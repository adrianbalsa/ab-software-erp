from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.constants import COSTE_OPERATIVO_EUR_KM
from app.core.plans import CostMeter
from app.db.supabase import SupabaseAsync
from app.services.geo_service import (
    GeoBatchCache,
    GeoService,
    _geo_cache_ttl_seconds,
    _get_redis_client,
    normalize_addr,
    record_maps_redis_meter,
    route_cache_key,
)
from app.services.usage_quota_service import UsageQuotaService

_log = logging.getLogger(__name__)

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
_ROUTES_API_V2_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
_MAPS_REDIS_PREFIX = "scanner:maps:v1"


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


def _truck_route_redis_key(
    tenant_empresa_id: str | UUID | None,
    origin: str,
    destination: str,
    weight: float | None,
    height: float | None,
    width: float | None,
    length: float | None,
    emission_type: str | None,
    waypoints: list[str] | None,
) -> str:
    tid = str(tenant_empresa_id).strip() if tenant_empresa_id is not None else ""
    tid = tid or "global"
    wp_norm = [normalize_addr(w) for w in (waypoints or []) if (w or "").strip()]
    payload = {
        "d": normalize_addr(destination),
        "e": str(emission_type or "EURO_VI").strip().upper(),
        "h": round(float(height or 0.0), 4),
        "l": round(float(length or 0.0), 4),
        "o": normalize_addr(origin),
        "w": round(float(weight or 0.0), 4),
        "wi": round(float(width or 0.0), 4),
        "wp": wp_norm,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fp = hashlib.sha256(raw).hexdigest()
    return f"{_MAPS_REDIS_PREFIX}:truck:{tid}:{fp}"


def _dm_redis_key(mem_key: str) -> str:
    return f"{_MAPS_REDIS_PREFIX}:dm:{mem_key}"


async def _redis_get_json(key: str) -> dict[str, Any] | None:
    client = await _get_redis_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if not raw:
            return None
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except Exception as exc:
        _log.debug("maps redis cache read skipped: %s", exc)
        return None


async def _redis_set_json(key: str, payload: dict[str, Any]) -> None:
    client = await _get_redis_client()
    if client is None:
        return
    try:
        await client.set(
            key,
            json.dumps(payload, separators=(",", ":")),
            ex=_geo_cache_ttl_seconds(),
        )
    except Exception as exc:
        _log.debug("maps redis cache write skipped: %s", exc)


class MapsService:
    """
    Distancias vía Google Distance Matrix API con caché en memoria + tabla
    ``maps_distance_cache`` (si existe y RLS permite).
    """

    def __init__(
        self,
        db: SupabaseAsync | None = None,
        quota_service: UsageQuotaService | None = None,
    ) -> None:
        self._db = db
        self._quota_service = quota_service
        self._geo = GeoService(db, quota_service)
        self._mem: dict[str, float] = {}
        self._route_mem: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def _consume_maps_quota(self, tenant_empresa_id: str | UUID | None) -> None:
        eid = str(tenant_empresa_id or "").strip()
        if not eid or self._quota_service is None:
            return
        await self._quota_service.consume(empresa_id=eid, meter=CostMeter.MAPS)

    @staticmethod
    def calculate_operational_cost(distance_km: float) -> float:
        return round(max(0.0, float(distance_km)) * float(COSTE_OPERATIVO_EUR_KM), 2)

    async def get_route_data(
        self,
        origin: str,
        destination: str,
        *,
        batch: GeoBatchCache | None = None,
        tenant_empresa_id: str | UUID | None = None,
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

        out = await self._geo.get_route_data(
            o,
            d,
            batch=batch,
            tenant_empresa_id=str(tenant_empresa_id) if tenant_empresa_id is not None else None,
        )
        async with self._lock:
            self._route_mem[route_key] = out
        return dict(out)

    @staticmethod
    def maps_api_key() -> str | None:
        return get_settings().maps_api_key

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

        rcli = await _get_redis_client()
        if rcli is not None:
            rd = await _redis_get_json(_dm_redis_key(mem_key))
            if rd is not None and rd.get("distance_km") is not None:
                km_redis = float(rd["distance_km"])
                async with self._lock:
                    self._mem[mem_key] = km_redis
                await record_maps_redis_meter(kind="distance_matrix", hit=True)
                return km_redis
            await record_maps_redis_meter(kind="distance_matrix", hit=False)

        cached = await self._load_db_cache(key, tenant_empresa_id)
        if cached is not None:
            async with self._lock:
                self._mem[mem_key] = cached
            await _redis_set_json(_dm_redis_key(mem_key), {"distance_km": cached})
            return cached

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "Maps_API_KEY no configurada: indique km_estimados manualmente o defina la clave de Google Maps"
            )

        await self._consume_maps_quota(tenant_empresa_id)
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
        await _redis_set_json(_dm_redis_key(mem_key), {"distance_km": km})
        return km

    async def geocode_lat_lng(
        self,
        address: str,
        *,
        batch: GeoBatchCache | None = None,
        tenant_empresa_id: str | UUID | None = None,
    ) -> tuple[float, float] | None:
        """
        Geocodificación (lat, lng) vía Geocoding API con caché en ``geo_cache`` + RAM.
        """
        return await self._geo.get_coordinates(
            address,
            batch=batch,
            tenant_empresa_id=str(tenant_empresa_id) if tenant_empresa_id is not None else None,
        )

    async def try_porte_geo_payload(
        self,
        origen: str,
        destino: str,
        *,
        tenant_empresa_id: str | UUID | None = None,
    ) -> dict[str, Any]:
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
            co = await self._geo.get_coordinates(
                o,
                batch=batch,
                tenant_empresa_id=str(tenant_empresa_id) if tenant_empresa_id is not None else None,
            )
            if co:
                out["lat_origin"] = float(co[0])
                out["lng_origin"] = float(co[1])
        except Exception:
            pass
        try:
            cd = await self._geo.get_coordinates(
                d,
                batch=batch,
                tenant_empresa_id=str(tenant_empresa_id) if tenant_empresa_id is not None else None,
            )
            if cd:
                out["lat_dest"] = float(cd[0])
                out["lng_dest"] = float(cd[1])
        except Exception:
            pass
        try:
            rd = await self._geo.get_route_data(
                o,
                d,
                batch=batch,
                tenant_empresa_id=str(tenant_empresa_id) if tenant_empresa_id is not None else None,
            )
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

        rcli = await _get_redis_client()
        if rcli is not None:
            rd = await _redis_get_json(_dm_redis_key(mem_key))
            if rd is not None and rd.get("distance_km") is not None:
                km_redis = float(rd["distance_km"])
                async with self._lock:
                    self._mem[mem_key] = km_redis
                await record_maps_redis_meter(kind="distance_matrix", hit=True)
                return km_redis, self._estimate_duration_minutes(km_redis)
            await record_maps_redis_meter(kind="distance_matrix", hit=False)

        cached = await self._load_db_cache(key, tenant_empresa_id)
        if cached is not None:
            async with self._lock:
                self._mem[mem_key] = cached
            await _redis_set_json(_dm_redis_key(mem_key), {"distance_km": cached})
            return cached, self._estimate_duration_minutes(cached)

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "Maps_API_KEY no configurada: indique km_estimados manualmente o defina la clave de Google Maps"
            )

        await self._consume_maps_quota(tenant_empresa_id)
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
        await _redis_set_json(_dm_redis_key(mem_key), {"distance_km": km})
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
        *,
        tenant_empresa_id: str | UUID | None = None,
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
                "Maps_API_KEY no configurada: indique km manualmente o defina la clave de Google Maps"
            )

        await self._consume_maps_quota(tenant_empresa_id)
        wp = [w.strip() for w in (waypoints or []) if (w or "").strip()]

        raw = await asyncio.to_thread(
            _directions_api_sync,
            o,
            d,
            wp if wp else None,
            api_key,
        )
        return _parse_directions_response(raw)

    async def get_truck_route(
        self,
        origin: str,
        destination: str,
        *,
        weight: float | None = None,
        height: float | None = None,
        width: float | None = None,
        length: float | None = None,
        emission_type: str | None = "EURO_VI",
        waypoints: list[str] | None = None,
        tenant_empresa_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        """
        Google Routes API v2 para vehículo pesado.
        Incluye RouteModifiers y vehicleInfo para casos de logística truck.
        """
        o = (origin or "").strip()
        d = (destination or "").strip()
        if not o or not d:
            raise ValueError("origin y destination son obligatorios")
        if normalize_addr(o) == normalize_addr(d):
            return {
                "distancia_km": 0.0,
                "tiempo_estimado_min": 0,
                "distance_meters": 0,
                "duration_seconds": 0,
                "tiene_peajes": False,
                "peajes_estimados_eur": 0.0,
                "travel_mode": "DRIVE",
                "vehicle_type": "HEAVY_TRUCK",
            }

        truck_rkey = _truck_route_redis_key(
            tenant_empresa_id,
            o,
            d,
            weight,
            height,
            width,
            length,
            emission_type,
            waypoints,
        )
        rcli = await _get_redis_client()
        if rcli is not None:
            tr_cached = await _redis_get_json(truck_rkey)
            if tr_cached is not None and tr_cached.get("distancia_km") is not None:
                await record_maps_redis_meter(kind="truck", hit=True)
                return dict(tr_cached)
            await record_maps_redis_meter(kind="truck", hit=False)

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "Maps_API_KEY no configurada: indique km manualmente o defina la clave de Google Maps"
            )

        await self._consume_maps_quota(tenant_empresa_id)
        try:
            import sentry_sdk
        except ImportError:
            sentry_sdk = None  # type: ignore[assignment]

        span_cm = (
            sentry_sdk.start_span(op="maps.routing", name="calculate_heavy_vehicle_route")
            if sentry_sdk
            else None
        )
        if span_cm is None:
            result = await self._compute_truck_route_impl(
                origin=o,
                destination=d,
                api_key=api_key,
                weight=weight,
                height=height,
                width=width,
                length=length,
                emission_type=emission_type,
                waypoints=waypoints,
                span=None,
            )
        else:
            with span_cm as span:
                result = await self._compute_truck_route_impl(
                    origin=o,
                    destination=d,
                    api_key=api_key,
                    weight=weight,
                    height=height,
                    width=width,
                    length=length,
                    emission_type=emission_type,
                    waypoints=waypoints,
                    span=span,
                )
        await _redis_set_json(truck_rkey, dict(result))
        return result

    async def _compute_truck_route_impl(
        self,
        *,
        origin: str,
        destination: str,
        api_key: str,
        weight: float | None,
        height: float | None,
        width: float | None,
        length: float | None,
        emission_type: str | None,
        waypoints: list[str] | None,
        span: Any | None,
    ) -> dict[str, Any]:
        vehicle_info = {
            "emissionType": _normalize_routes_emission_type(emission_type),
        }
        if span is not None:
            span.set_data("travel_mode", "DRIVE")
            span.set_data("vehicle_type", "HEAVY_TRUCK")
            span.set_data("truck_weight_kg", max(0.0, float(weight or 0.0)))
            span.set_data("truck_height_m", max(0.0, float(height or 0.0)))
            span.set_data("truck_width_m", max(0.0, float(width or 0.0)))
            span.set_data("truck_length_m", max(0.0, float(length or 0.0)))
            span.set_data("truck_emission_type", vehicle_info["emissionType"])

        payload: dict[str, Any] = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "routeModifiers": {
                "avoidTolls": False,
                "avoidHighways": False,
                "avoidFerries": False,
                "vehicleInfo": vehicle_info,
            },
            "extraComputations": ["TOLLS"],
            "units": "METRIC",
        }
        wp = [w.strip() for w in (waypoints or []) if (w or "").strip()]
        if wp:
            payload["intermediates"] = [{"address": w} for w in wp]

        headers = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "routes.distanceMeters,routes.duration,routes.travelAdvisory.tollInfo"
            ),
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            resp = await client.post(_ROUTES_API_V2_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        routes = data.get("routes") or []
        if not routes:
            raise ValueError("Routes API v2: sin rutas para vehículo pesado")
        route = routes[0]
        meters = int(route.get("distanceMeters") or 0)
        duration_seconds = _duration_to_seconds(route.get("duration"))
        km = 0.0 if meters <= 0 else round(meters / 1000.0, 4)
        mins = (
            MapsService._estimate_duration_minutes(km)
            if duration_seconds <= 0
            else max(0, int(round(duration_seconds / 60.0)))
        )
        tolls = _parse_toll_amount_eur(route.get("travelAdvisory") or {})
        fuel_cost_estimate = None
        try:
            from app.core.math_engine import MathEngine

            costs = MathEngine.calculate_route_costs(
                distance_km=km,
                toll_cost=tolls,
            )
            fuel_cost_estimate = float(costs.get("fuel_cost_estimate") or 0.0)
        except Exception:
            fuel_cost_estimate = None
        if span is not None:
            span.set_data("distance_km", km)
            span.set_data("duration_minutes", mins)
            span.set_data("toll_cost_estimate", tolls)
            if fuel_cost_estimate is not None:
                span.set_data("fuel_cost_estimate", fuel_cost_estimate)
        return {
            "distancia_km": km,
            "tiempo_estimado_min": mins,
            "distance_meters": meters,
            "duration_seconds": duration_seconds,
            "tiene_peajes": tolls > 0.0,
            "peajes_estimados_eur": tolls,
            "travel_mode": "DRIVE",
            "vehicle_type": "HEAVY_TRUCK",
        }


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


def _normalize_routes_emission_type(raw: str | None) -> str:
    val = str(raw or "").strip().upper()
    if "ELECT" in val:
        return "ELECTRIC"
    if "HYBRID" in val or "HIBRID" in val:
        return "HYBRID"
    if "CNG" in val:
        return "CNG"
    if "GAS" in val and "DIESEL" not in val:
        return "GASOLINE"
    # EURO_VI / EURO VI se mapea a diésel por compatibilidad del enum Routes v2.
    return "DIESEL"


def _duration_to_seconds(raw: Any) -> int:
    if isinstance(raw, str) and raw.endswith("s"):
        try:
            return max(0, int(float(raw[:-1])))
        except (TypeError, ValueError):
            return 0
    return 0


def _parse_toll_amount_eur(travel_advisory: dict[str, Any]) -> float:
    toll_info = travel_advisory.get("tollInfo") if isinstance(travel_advisory, dict) else None
    if not isinstance(toll_info, dict):
        return 0.0
    prices = toll_info.get("estimatedPrice")
    if not isinstance(prices, list):
        return 0.0
    total_eur = 0.0
    for p in prices:
        if not isinstance(p, dict):
            continue
        code = str(p.get("currencyCode") or "").upper().strip()
        if code and code != "EUR":
            continue
        units = float(p.get("units") or 0.0)
        nanos = float(p.get("nanos") or 0.0)
        total_eur += units + (nanos / 1_000_000_000.0)
    return round(max(0.0, total_eur), 2)


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
