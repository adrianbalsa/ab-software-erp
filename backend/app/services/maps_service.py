from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from uuid import UUID

import anyio
import httpx

from app.db.supabase import SupabaseAsync
from app.services.geo_service import GeoBatchCache, GeoService, normalize_addr, route_cache_key

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def _cache_key(origin: str, destination: str) -> str:
    return route_cache_key(origin, destination)


def _mem_storage_key(tenant_empresa_id: str | UUID | None, route_key: str) -> str:
    """Evita compartir caché en RAM entre tenants en el mismo worker."""
    if tenant_empresa_id is None:
        return route_key
    t = str(tenant_empresa_id).strip()
    if not t:
        return route_key
    return f"{t}:{route_key}"


class MapsService:
    """
    Distancias vía Google Distance Matrix API con caché en memoria + tabla
    ``maps_distance_cache`` (si existe y RLS permite).
    """

    def __init__(self, db: SupabaseAsync | None = None) -> None:
        self._db = db
        self._geo = GeoService(db)
        self._mem: dict[str, float] = {}
        self._route_mem: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def calculate_operational_cost(distance_km: float) -> float:
        return round(max(0.0, float(distance_km)) * 0.62, 2)

    async def get_route_data(
        self,
        origin: str,
        destination: str,
        *,
        batch: GeoBatchCache | None = None,
    ) -> dict[str, Any]:
        """
        Cache-first route lookup backed by ``geo_cache`` (Routes API v2 en ``GeoService``).
        Retorna:
        { distance_meters, duration_seconds, distance_km, duration_mins, estimated_cost, source }
        """
        o = (origin or "").strip()
        d = (destination or "").strip()
        if not o or not d:
            raise ValueError("origin y destination son obligatorios")

        route_key = _cache_key(o, d)
        async with self._lock:
            mem_row = self._route_mem.get(route_key)
            if mem_row is not None:
                return dict(mem_row)

        out = await self._geo.get_route_data(o, d, batch=batch)
        async with self._lock:
            self._route_mem[route_key] = out
        return dict(out)

    @staticmethod
    def maps_api_key() -> str | None:
        return (
            os.getenv("Maps_API_KEY")
            or os.getenv("MAPS_API_KEY")
            or os.getenv("GOOGLE_MAPS_API_KEY")
            or ""
        ).strip() or None

    async def get_distance_km(
        self,
        origin: str,
        destination: str,
        *,
        tenant_empresa_id: str | UUID | None = None,
    ) -> float:
        """
        Distancia en km (ruta carretera preferente). Usa caché antes de llamar a Google.
        ``tenant_empresa_id`` acota la caché Postgres (RLS por empresa); si es None, solo RAM.
        """
        o = (origin or "").strip()
        d = (destination or "").strip()
        if not o or not d:
            raise ValueError("Origen y destino son obligatorios para calcular la distancia")
        if normalize_addr(o) == normalize_addr(d):
            return 0.0

        key = _cache_key(o, d)
        mem_key = _mem_storage_key(tenant_empresa_id, key)
        async with self._lock:
            if mem_key in self._mem:
                return float(self._mem[mem_key])

        cached = await self._load_db_cache(key, tenant_empresa_id)
        if cached is not None:
            async with self._lock:
                self._mem[mem_key] = cached
            return cached

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "MAPS_API_KEY no configurada: indique km_estimados manualmente o defina la clave de Google Maps"
            )

        km, _duration_min = await self._fetch_distance_matrix(
            origin=o,
            destination=d,
            api_key=api_key,
        )

        async with self._lock:
            self._mem[mem_key] = km
        await self._save_db_cache(
            key=key,
            origin=o,
            destination=d,
            km=km,
            tenant_empresa_id=tenant_empresa_id,
        )
        return km

    async def geocode_lat_lng(
        self,
        address: str,
        *,
        batch: GeoBatchCache | None = None,
    ) -> tuple[float, float] | None:
        """
        Geocodificación (lat, lng) vía Geocoding API con caché en ``geo_cache`` + RAM.
        """
        return await self._geo.get_coordinates(address, batch=batch)

    async def try_porte_geo_payload(self, origen: str, destino: str) -> dict[str, Any]:
        """
        Coordenadas origen/destino + distancia real (m) para persistir en ``portes``.
        Falla de API o clave ausente → dict vacío (no bloquea alta de porte).
        """
        out: dict[str, Any] = {}
        o = (origen or "").strip()
        d = (destino or "").strip()
        if not o or not d:
            return out
        batch = GeoBatchCache()
        try:
            co = await self._geo.get_coordinates(o, batch=batch)
            if co:
                out["lat_origin"] = float(co[0])
                out["lng_origin"] = float(co[1])
        except Exception:
            pass
        try:
            cd = await self._geo.get_coordinates(d, batch=batch)
            if cd:
                out["lat_dest"] = float(cd[0])
                out["lng_dest"] = float(cd[1])
        except Exception:
            pass
        try:
            rd = await self._geo.get_route_data(o, d, batch=batch)
            dm = rd.get("distance_meters")
            if dm is not None:
                out["real_distance_meters"] = float(dm)
        except Exception:
            pass
        return out

    async def get_distance_and_duration(
        self,
        origin: str,
        destination: str,
        *,
        tenant_empresa_id: str | UUID | None = None,
    ) -> tuple[float, int]:
        """
        Distancia en km y duración estimada en minutos.
        Si la distancia viene de caché sin duración persistida, estima duración con 70 km/h.
        """
        o = (origin or "").strip()
        d = (destination or "").strip()
        if not o or not d:
            raise ValueError("Origen y destino son obligatorios para calcular la distancia")
        if normalize_addr(o) == normalize_addr(d):
            return 0.0, 0

        key = _cache_key(o, d)
        mem_key = _mem_storage_key(tenant_empresa_id, key)
        async with self._lock:
            if mem_key in self._mem:
                km = float(self._mem[mem_key])
                return km, self._estimate_duration_minutes(km)

        cached = await self._load_db_cache(key, tenant_empresa_id)
        if cached is not None:
            async with self._lock:
                self._mem[mem_key] = cached
            return cached, self._estimate_duration_minutes(cached)

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "MAPS_API_KEY no configurada: indique km_estimados manualmente o defina la clave de Google Maps"
            )

        km, duration_min = await self._fetch_distance_matrix(
            origin=o,
            destination=d,
            api_key=api_key,
        )
        async with self._lock:
            self._mem[mem_key] = km
        await self._save_db_cache(
            key=key,
            origin=o,
            destination=d,
            km=km,
            tenant_empresa_id=tenant_empresa_id,
        )
        return km, duration_min

    async def _load_db_cache(
        self,
        cache_key: str,
        tenant_empresa_id: str | UUID | None,
    ) -> float | None:
        if self._db is None:
            return None
        eid = (str(tenant_empresa_id).strip() if tenant_empresa_id is not None else "")
        if not eid:
            return None
        try:
            q = (
                self._db.table("maps_distance_cache")
                .select("distance_km")
                .eq("empresa_id", eid)
                .eq("cache_key", cache_key)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return None
            return float(rows[0].get("distance_km") or 0.0)
        except Exception:
            return None

    async def _save_db_cache(
        self,
        *,
        key: str,
        origin: str,
        destination: str,
        km: float,
        tenant_empresa_id: str | UUID | None,
    ) -> None:
        if self._db is None:
            return
        eid = (str(tenant_empresa_id).strip() if tenant_empresa_id is not None else "")
        if not eid:
            return
        try:
            payload = {
                "empresa_id": eid,
                "cache_key": key,
                "origin": origin[:500],
                "destination": destination[:500],
                "distance_km": round(km, 4),
            }
            q = self._db.table("maps_distance_cache").upsert(
                payload,
                on_conflict="empresa_id,cache_key",
            )
            await self._db.execute(q)
        except Exception:
            pass

    @staticmethod
    async def _fetch_distance_matrix(
        *,
        origin: str,
        destination: str,
        api_key: str,
    ) -> tuple[float, int]:
        params = {
            "origins": origin,
            "destinations": destination,
            "units": "metric",
            "key": api_key,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            resp = await client.get(_DISTANCE_MATRIX_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        status = str(data.get("status") or "")
        if status != "OK":
            raise ValueError(f"Distance Matrix API: {status}")

        rows = data.get("rows") or []
        if not rows:
            raise ValueError("Distance Matrix: sin filas")
        elements = rows[0].get("elements") or []
        if not elements:
            raise ValueError("Distance Matrix: sin elementos")
        el = elements[0]
        el_status = str(el.get("status") or "")
        if el_status != "OK":
            raise ValueError(f"Distance Matrix elemento: {el_status}")

        dist = el.get("distance") or {}
        meters = float(dist.get("value") or 0.0)
        dur = el.get("duration") or {}
        duration_seconds = int(dur.get("value") or 0)
        km = 0.0 if meters <= 0 else round(meters / 1000.0, 4)
        if duration_seconds <= 0:
            return km, MapsService._estimate_duration_minutes(km)
        return km, max(0, int(round(duration_seconds / 60.0)))

    @staticmethod
    def _estimate_duration_minutes(km: float) -> int:
        # Fallback conservador para rutas mixtas cuando no hay duración exacta en caché.
        if km <= 0:
            return 0
        return max(1, int(round((km / 70.0) * 60.0)))

    async def calcular_ruta_optima(
        self,
        origen: str,
        destino: str,
        waypoints: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Directions API (googlemaps) con tráfico: distancia exacta, duración con tráfico y peajes.

        La llamada al cliente síncrono de Google se ejecuta en un thread pool para no bloquear el event loop.
        """
        o = (origen or "").strip()
        d = (destino or "").strip()
        if not o or not d:
            raise ValueError("Origen y destino son obligatorios")
        if normalize_addr(o) == normalize_addr(d):
            return {
                "distancia_km": 0.0,
                "tiempo_estimado_min": 0,
                "tiene_peajes": False,
            }

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "Maps_API_KEY / MAPS_API_KEY no configurada: indique km manualmente o defina la clave de Google Maps"
            )

        wp = [w.strip() for w in (waypoints or []) if (w or "").strip()]

        raw = await anyio.to_thread.run_sync(
            _directions_api_sync,
            o,
            d,
            wp if wp else None,
            api_key,
        )
        return _parse_directions_response(raw)


def _directions_api_sync(
    origin: str,
    destination: str,
    waypoints: list[str] | None,
    api_key: str,
) -> list[dict[str, Any]]:
    import googlemaps

    client = googlemaps.Client(key=api_key)
    kwargs: dict[str, Any] = {
        "mode": "driving",
        "departure_time": int(time.time()),
        "traffic_model": "best_guess",
    }
    if waypoints:
        kwargs["waypoints"] = waypoints
    return client.directions(origin, destination, **kwargs)


def _route_has_tolls(route: dict[str, Any]) -> bool:
    for w in route.get("warnings") or []:
        ws = str(w).lower()
        if "toll" in ws or "peaje" in ws:
            return True
    for leg in route.get("legs") or []:
        for step in leg.get("steps") or []:
            html = str(step.get("html_instructions") or "").lower()
            if "toll" in html or "peaje" in html or "autopista de peaje" in html:
                return True
            man = step.get("maneuver")
            if isinstance(man, str) and "toll" in man.lower():
                return True
    blob = json.dumps(route, ensure_ascii=False).lower()
    return "toll" in blob


def _parse_directions_response(routes: list[dict[str, Any]]) -> dict[str, Any]:
    if not routes:
        raise ValueError("Directions API: sin rutas")
    route = routes[0]
    legs = route.get("legs") or []
    if not legs:
        raise ValueError("Directions API: sin tramos")

    dist_m = 0.0
    dur_traffic_s = 0
    has_traffic = False
    for leg in legs:
        dist_m += float((leg.get("distance") or {}).get("value") or 0.0)
        dit = leg.get("duration_in_traffic")
        if isinstance(dit, dict) and dit.get("value") is not None:
            dur_traffic_s += int(dit.get("value") or 0)
            has_traffic = True
        else:
            dur_traffic_s += int((leg.get("duration") or {}).get("value") or 0)

    km = 0.0 if dist_m <= 0 else round(dist_m / 1000.0, 4)
    if dur_traffic_s <= 0:
        mins = MapsService._estimate_duration_minutes(km)
    else:
        mins = max(0, int(round(dur_traffic_s / 60.0)))

    tiene_peajes = _route_has_tolls(route)

    return {
        "distancia_km": km,
        "tiempo_estimado_min": mins,
        "tiene_peajes": tiene_peajes,
        "duracion_con_trafico": has_traffic,
    }
