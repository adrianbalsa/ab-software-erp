from __future__ import annotations

import json
import re
from typing import Any

_COORDS_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class GeoCache:
    """Cache-aside Redis wrapper for external route APIs."""

    SAVINGS_KEY = "stats:total_savings_euros"
    METRICS_KEY = "stats:routes_cache_metrics"
    SAVINGS_PER_HIT_EUR = 0.015

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    @staticmethod
    def normalize_coords(lat: float, lng: float) -> tuple[float, float]:
        """Normalize coordinates at ~11m precision for cache reuse."""
        return round(float(lat), 4), round(float(lng), 4)

    @classmethod
    def _normalize_location(cls, location: str) -> str:
        value = (location or "").strip()
        if not value:
            return value
        match = _COORDS_PATTERN.match(value)
        if not match:
            return value.lower()
        lat, lng = cls.normalize_coords(float(match.group(1)), float(match.group(2)))
        return f"{lat:.4f},{lng:.4f}"

    @classmethod
    def route_key(cls, vehicle_profile: str, origin: str, destination: str) -> str:
        profile = (vehicle_profile or "default").strip().lower()
        normalized_origin = cls._normalize_location(origin)
        normalized_destination = cls._normalize_location(destination)
        return f"route:{profile}:{normalized_origin}:{normalized_destination}"

    async def get_route(self, key: str) -> dict[str, Any] | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
            await self._record_cache_access(hit=bool(raw))
            if not raw:
                return None
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    async def set_route(self, key: str, payload: dict[str, Any], ttl_seconds: int = 24 * 60 * 60) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                key,
                json.dumps(payload, separators=(",", ":")),
                ex=max(60, int(ttl_seconds)),
            )
        except Exception:
            return

    async def _record_cache_access(self, *, hit: bool) -> None:
        if self._redis is None:
            return
        try:
            if hit:
                await self._redis.incrbyfloat(self.SAVINGS_KEY, self.SAVINGS_PER_HIT_EUR)
                await self._redis.hincrby(self.METRICS_KEY, "hits", 1)
            else:
                await self._redis.hincrby(self.METRICS_KEY, "misses", 1)
        except Exception:
            return

    async def economics_metrics(self) -> dict[str, float]:
        if self._redis is None:
            return {"total_savings_euros": 0.0, "hit_rate": 0.0, "hits": 0.0, "misses": 0.0}
        try:
            raw_savings = await self._redis.get(self.SAVINGS_KEY)
            savings = float(raw_savings or 0.0)
            stats = await self._redis.hgetall(self.METRICS_KEY)
            hits = float(stats.get("hits") or 0.0)
            misses = float(stats.get("misses") or 0.0)
            total = hits + misses
            hit_rate = round(hits / total, 4) if total > 0 else 0.0
            return {
                "total_savings_euros": round(savings, 4),
                "hit_rate": hit_rate,
                "hits": hits,
                "misses": misses,
            }
        except Exception:
            return {"total_savings_euros": 0.0, "hit_rate": 0.0, "hits": 0.0, "misses": 0.0}
