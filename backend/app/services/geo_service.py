from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.db.supabase import SupabaseAsync

_log = logging.getLogger(__name__)

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_ROUTES_V2_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
_GEO_CACHE_TABLE = "geo_cache"
_GEO_CACHE_TTL_DAYS = 30

# Redundant punctuation / whitespace for stable geocode & route cache keys.
_RE_NORMALIZE_PUNCT = re.compile(r"[,;.]+")
_RE_NORMALIZE_SPACE = re.compile(r"\s+")


def normalize_addr(s: str) -> str:
    """Delegación a la normalización canónica de ``GeoService`` (claves de caché)."""
    return GeoService._normalize_address(s)


def route_cache_key(origin: str, destination: str) -> str:
    a = GeoService._normalize_address(origin)
    b = GeoService._normalize_address(destination)
    raw = f"{a}|{b}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def geocode_cache_key(address: str) -> str:
    n = GeoService._normalize_address(address)
    raw = f"gc|{n}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class GeoBatchCache:
    """
    Caché de scoped request (p.ej. un alta de porte con varias consultas) para evitar
    lecturas repetidas a DB / RAM del servicio entre llamadas relacionadas.
    """

    __slots__ = ("_coords", "_routes")

    def __init__(self) -> None:
        self._coords: dict[str, tuple[float, float]] = {}
        self._routes: dict[str, dict[str, Any]] = {}


def _parse_duration_seconds(raw: Any) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return max(0, int(round(float(raw))))
    s = str(raw).strip()
    m = re.match(r"^(\d+)(?:\.\d+)?s$", s, re.IGNORECASE)
    if m:
        return max(0, int(round(float(m.group(1)))))
    m2 = re.match(r"^(\d+)", s)
    if m2:
        return max(0, int(round(float(m2.group(1)))))
    return 0


class GeoService:
    """
    Google Geocoding API + Routes API (v2) con persistencia en ``public.geo_cache``.
    """

    def __init__(self, db: SupabaseAsync | None = None) -> None:
        self._db = db
        self._lock = asyncio.Lock()
        self._mem_coords: dict[str, tuple[float, float]] = {}
        self._mem_route: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _normalize_address(address: str) -> str:
        """
        Normalización canónica para claves de caché: trim, minúsculas, puntuación
        redundante unificada y espacios colapsados.
        """
        if not address:
            return ""
        s = address.strip().lower()
        s = _RE_NORMALIZE_PUNCT.sub(" ", s)
        s = _RE_NORMALIZE_SPACE.sub(" ", s).strip()
        return s

    @staticmethod
    def maps_api_key() -> str | None:
        return (
            os.getenv("Maps_API_KEY")
            or os.getenv("MAPS_API_KEY")
            or os.getenv("GOOGLE_MAPS_API_KEY")
            or ""
        ).strip() or None

    async def get_coordinates(
        self,
        address: str,
        *,
        batch: GeoBatchCache | None = None,
    ) -> tuple[float, float] | None:
        """Geocodifica una dirección; resultados cacheados en ``geo_cache`` (kind=geocode)."""
        raw = (address or "").strip()
        if not raw:
            return None

        no = self._normalize_address(raw)
        gkey = geocode_cache_key(raw)

        if batch is not None and gkey in batch._coords:
            return batch._coords[gkey]

        async with self._lock:
            if gkey in self._mem_coords:
                return self._mem_coords[gkey]

        cached = await self._load_geocode_cache(gkey, normalized=no)
        if cached is not None:
            async with self._lock:
                self._mem_coords[gkey] = cached
            if batch is not None:
                batch._coords[gkey] = cached
            return cached

        api_key = self.maps_api_key()
        if not api_key:
            return None

        params = {"address": raw[:500], "key": api_key}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(14.0)) as client:
                resp = await client.get(_GEOCODE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            _log.warning("Geocoding API error: %s", exc)
            return None

        if str(data.get("status") or "") != "OK":
            return None
        results = data.get("results") or []
        if not results:
            return None
        r0 = results[0]
        loc = (r0.get("geometry") or {}).get("location") or {}
        try:
            lat = float(loc.get("lat"))
            lng = float(loc.get("lng"))
        except (TypeError, ValueError):
            return None

        formatted = str(r0.get("formatted_address") or "").strip()

        await self._save_geocode_cache(
            route_key=gkey,
            address=raw,
            normalized=no,
            lat=lat,
            lng=lng,
        )
        if formatted:
            await self._maybe_save_geocode_alias(
                formatted_address=formatted,
                lat=lat,
                lng=lng,
                primary_key=gkey,
            )

        pt = (lat, lng)
        async with self._lock:
            self._mem_coords[gkey] = pt
        if batch is not None:
            batch._coords[gkey] = pt
        return pt

    async def _maybe_save_geocode_alias(
        self,
        *,
        formatted_address: str,
        lat: float,
        lng: float,
        primary_key: str,
    ) -> None:
        alias_key = geocode_cache_key(formatted_address)
        if alias_key == primary_key:
            return
        an = self._normalize_address(formatted_address)
        await self._save_geocode_cache(
            route_key=alias_key,
            address=formatted_address[:500],
            normalized=an,
            lat=lat,
            lng=lng,
        )

    async def get_route_data(
        self,
        origin: str,
        destination: str,
        *,
        batch: GeoBatchCache | None = None,
    ) -> dict[str, Any]:
        """
        Distancia (m) y duración (s) vía Routes API v2 ``computeRoutes``.
        Devuelve también km y minutos para compatibilidad con callers existentes.
        """
        o = (origin or "").strip()
        d = (destination or "").strip()
        if not o or not d:
            raise ValueError("origin y destination son obligatorios")

        no = self._normalize_address(o)
        nd = self._normalize_address(d)
        if no == nd:
            z = self._route_response_from_meters(
                distance_meters=0.0,
                duration_seconds=0,
                source="trivial",
            )
            if batch is not None:
                rk0 = route_cache_key(o, d)
                batch._routes[rk0] = dict(z)
            return dict(z)

        rkey = route_cache_key(o, d)

        if batch is not None and rkey in batch._routes:
            return dict(batch._routes[rkey])

        async with self._lock:
            mem = self._mem_route.get(rkey)
            if mem is not None:
                return dict(mem)

        cached = await self._load_route_cache(
            route_key=rkey,
            normalized_origin=no,
            normalized_destination=nd,
        )
        if cached is not None:
            built = self._route_response_from_meters(
                distance_meters=float(cached["distance_meters"]),
                duration_seconds=int(cached["duration_seconds"]),
                source="cache",
            )
            async with self._lock:
                self._mem_route[rkey] = built
            if batch is not None:
                batch._routes[rkey] = dict(built)
            return dict(built)

        rev_key = route_cache_key(d, o)

        async def _from_reversed(
            distance_meters: float, duration_seconds: int, *, src: str
        ) -> dict[str, Any]:
            built = self._route_response_from_meters(
                distance_meters=distance_meters,
                duration_seconds=int(duration_seconds),
                source=src,
            )
            async with self._lock:
                self._mem_route[rkey] = built
            if batch is not None:
                batch._routes[rkey] = dict(built)
            return dict(built)

        if batch is not None and rev_key in batch._routes:
            bm = batch._routes[rev_key]
            return await _from_reversed(
                float(bm["distance_meters"]),
                int(bm["duration_seconds"]),
                src="cache_reversed",
            )

        async with self._lock:
            rev_mem = self._mem_route.get(rev_key)
        if rev_mem is not None:
            return await _from_reversed(
                float(rev_mem["distance_meters"]),
                int(rev_mem["duration_seconds"]),
                src="cache_reversed",
            )

        rev = await self._load_route_cache(
            route_key=rev_key,
            normalized_origin=nd,
            normalized_destination=no,
        )
        if rev is not None:
            return await _from_reversed(
                float(rev["distance_meters"]),
                int(rev["duration_seconds"]),
                src="cache_reversed",
            )

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError("MAPS_API_KEY / GOOGLE_MAPS_API_KEY no configurada")

        distance_meters, duration_seconds = await self._compute_routes_v2(
            origin=o,
            destination=d,
            api_key=api_key,
        )
        await self._save_route_cache(
            route_key=rkey,
            origin=o,
            destination=d,
            normalized_origin=no,
            normalized_destination=nd,
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
        )
        built = self._route_response_from_meters(
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
            source="google",
        )
        async with self._lock:
            self._mem_route[rkey] = built
        if batch is not None:
            batch._routes[rkey] = dict(built)
        return dict(built)

    def _route_response_from_meters(
        self,
        *,
        distance_meters: float,
        duration_seconds: int,
        source: str,
    ) -> dict[str, Any]:
        dm = max(0.0, float(distance_meters))
        ds = max(0, int(duration_seconds))
        distance_km = round(dm / 1000.0, 3)
        duration_mins = max(0, int(round(ds / 60.0)))
        return {
            "distance_meters": int(round(dm)),
            "duration_seconds": ds,
            "distance_km": distance_km,
            "duration_mins": duration_mins,
            "estimated_cost": round(max(0.0, distance_km) * 0.62, 2),
            "source": source,
        }

    async def _compute_routes_v2(
        self,
        *,
        origin: str,
        destination: str,
        api_key: str,
    ) -> tuple[float, int]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
        }
        body: dict[str, Any] = {
            "origin": {"address": origin[:500]},
            "destination": {"address": destination[:500]},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            resp = await client.post(_ROUTES_V2_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        routes = data.get("routes") or []
        if not routes:
            raise ValueError("Routes API v2: sin rutas")
        r0 = routes[0]
        dm_raw = r0.get("distanceMeters")
        try:
            distance_meters = float(dm_raw or 0.0)
        except (TypeError, ValueError):
            distance_meters = 0.0
        duration_seconds = _parse_duration_seconds(r0.get("duration"))
        if distance_meters <= 0:
            raise ValueError("Routes API v2: distancia nula")
        return max(0.0, distance_meters), duration_seconds

    async def _load_geocode_cache(
        self,
        route_key: str,
        *,
        normalized: str,
    ) -> tuple[float, float] | None:
        if self._db is None:
            return None
        threshold = (datetime.now(timezone.utc) - timedelta(days=_GEO_CACHE_TTL_DAYS)).isoformat()
        try:
            q = (
                self._db.table(_GEO_CACHE_TABLE)
                .select("lat,lng,updated_at")
                .eq("route_key", route_key)
                .eq("cache_kind", "geocode")
                .gte("updated_at", threshold)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                q = (
                    self._db.table(_GEO_CACHE_TABLE)
                    .select("lat,lng,updated_at")
                    .eq("cache_kind", "geocode")
                    .eq("origin_norm", normalized[:500])
                    .gte("updated_at", threshold)
                    .limit(1)
                )
                res = await self._db.execute(q)
                rows = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return None
            row = rows[0]
            lat = float(row.get("lat") or 0.0)
            lng = float(row.get("lng") or 0.0)
            if lat == 0.0 and lng == 0.0:
                return None
            return lat, lng
        except Exception as exc:
            _log.debug("geocode cache read skipped: %s", exc)
            return None

    async def _load_route_cache(
        self,
        *,
        route_key: str,
        normalized_origin: str,
        normalized_destination: str,
    ) -> dict[str, float | int] | None:
        if self._db is None:
            return None
        threshold = (datetime.now(timezone.utc) - timedelta(days=_GEO_CACHE_TTL_DAYS)).isoformat()
        try:
            q = (
                self._db.table(_GEO_CACHE_TABLE)
                .select("distance_meters,duration_seconds,updated_at")
                .eq("route_key", route_key)
                .eq("cache_kind", "route")
                .gte("updated_at", threshold)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                q = (
                    self._db.table(_GEO_CACHE_TABLE)
                    .select("distance_meters,duration_seconds,updated_at")
                    .eq("cache_kind", "route")
                    .eq("origin_norm", normalized_origin[:500])
                    .eq("destination_norm", normalized_destination[:500])
                    .gte("updated_at", threshold)
                    .limit(1)
                )
                res = await self._db.execute(q)
                rows = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return None
            row = rows[0]
            distance_meters = float(row.get("distance_meters") or 0.0)
            duration_seconds = int(row.get("duration_seconds") or 0)
            if distance_meters < 0 or duration_seconds < 0:
                return None
            return {
                "distance_meters": distance_meters,
                "duration_seconds": duration_seconds,
            }
        except Exception as exc:
            _log.debug("route cache read skipped: %s", exc)
            return None

    async def _save_geocode_cache(
        self,
        *,
        route_key: str,
        address: str,
        normalized: str,
        lat: float,
        lng: float,
    ) -> None:
        if self._db is None:
            return
        try:
            payload = {
                "route_key": route_key,
                "cache_kind": "geocode",
                "origin": address[:500],
                "destination": "",
                "origin_norm": normalized[:500],
                "destination_norm": "",
                "distance_meters": 0,
                "duration_seconds": 0,
                "lat": float(lat),
                "lng": float(lng),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            q = self._db.table(_GEO_CACHE_TABLE).upsert(payload, on_conflict="route_key")
            await self._db.execute(q)
        except Exception as exc:
            _log.debug("geocode cache write skipped: %s", exc)

    async def _save_route_cache(
        self,
        *,
        route_key: str,
        origin: str,
        destination: str,
        normalized_origin: str,
        normalized_destination: str,
        distance_meters: float,
        duration_seconds: int,
    ) -> None:
        if self._db is None:
            return
        try:
            payload = {
                "route_key": route_key,
                "cache_kind": "route",
                "origin": origin[:500],
                "destination": destination[:500],
                "origin_norm": normalized_origin[:500],
                "destination_norm": normalized_destination[:500],
                "distance_meters": max(0, int(round(distance_meters))),
                "duration_seconds": max(0, int(duration_seconds)),
                "lat": None,
                "lng": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            q = self._db.table(_GEO_CACHE_TABLE).upsert(payload, on_conflict="route_key")
            await self._db.execute(q)
        except Exception as exc:
            _log.debug("route cache write skipped: %s", exc)
