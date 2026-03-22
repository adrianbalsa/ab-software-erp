from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any

import httpx

from app.db.supabase import SupabaseAsync

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def _normalize_addr(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _cache_key(origin: str, destination: str) -> str:
    a = _normalize_addr(origin)
    b = _normalize_addr(destination)
    raw = f"{a}|{b}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class MapsService:
    """
    Distancias vía Google Distance Matrix API con caché en memoria + tabla
    ``maps_distance_cache`` (si existe y RLS permite).
    """

    def __init__(self, db: SupabaseAsync | None = None) -> None:
        self._db = db
        self._mem: dict[str, float] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def maps_api_key() -> str | None:
        return (os.getenv("MAPS_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY") or "").strip() or None

    async def get_distance_km(self, origin: str, destination: str) -> float:
        """
        Distancia en km (ruta carretera preferente). Usa caché antes de llamar a Google.
        """
        o = (origin or "").strip()
        d = (destination or "").strip()
        if not o or not d:
            raise ValueError("Origen y destino son obligatorios para calcular la distancia")
        if _normalize_addr(o) == _normalize_addr(d):
            return 0.0

        key = _cache_key(o, d)
        async with self._lock:
            if key in self._mem:
                return float(self._mem[key])

        cached = await self._load_db_cache(key)
        if cached is not None:
            async with self._lock:
                self._mem[key] = cached
            return cached

        api_key = self.maps_api_key()
        if not api_key:
            raise ValueError(
                "MAPS_API_KEY no configurada: indique km_estimados manualmente o defina la clave de Google Maps"
            )

        km = await self._fetch_distance_matrix_km(
            origin=o,
            destination=d,
            api_key=api_key,
        )

        async with self._lock:
            self._mem[key] = km
        await self._save_db_cache(key=key, origin=o, destination=d, km=km)
        return km

    async def _load_db_cache(self, cache_key: str) -> float | None:
        if self._db is None:
            return None
        try:
            q = (
                self._db.table("maps_distance_cache")
                .select("distance_km")
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
    ) -> None:
        if self._db is None:
            return
        try:
            payload = {
                "cache_key": key,
                "origin": origin[:500],
                "destination": destination[:500],
                "distance_km": round(km, 4),
            }
            await self._db.execute(self._db.table("maps_distance_cache").upsert(payload))
        except Exception:
            pass

    @staticmethod
    async def _fetch_distance_matrix_km(
        *,
        origin: str,
        destination: str,
        api_key: str,
    ) -> float:
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
        if meters <= 0:
            return 0.0
        return round(meters / 1000.0, 4)
