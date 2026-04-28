"""Redis cache-aside for truck routes and distance matrix (Phase 2.1)."""

from __future__ import annotations

import json

import pytest

from app.services.geo_service import GeoService
from app.services.maps_service import MapsService, _truck_route_redis_key


class _FakeRedis:
    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self.values = dict(initial or {})
        self.hashes: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:  # noqa: ARG002
        self.values[key] = value

    async def hincrby(self, key: str, field: str, amount: int) -> None:
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = float(bucket.get(field, 0.0) + amount)

    async def incrbyfloat(self, key: str, amount: float) -> float:
        current = float(self.values.get(key) or 0.0)
        updated = current + float(amount)
        self.values[key] = str(updated)
        return updated

    async def hgetall(self, key: str) -> dict[str, float]:
        return dict(self.hashes.get(key, {}))


@pytest.mark.asyncio
async def test_truck_route_served_from_redis_without_maps_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.geo_service as geo
    import app.services.maps_service as ms

    payload = {
        "distancia_km": 100.0,
        "tiempo_estimado_min": 60,
        "distance_meters": 100_000,
        "duration_seconds": 3600,
        "tiene_peajes": False,
        "peajes_estimados_eur": 0.0,
        "travel_mode": "DRIVE",
        "vehicle_type": "HEAVY_TRUCK",
    }
    rkey = _truck_route_redis_key(
        None,
        "Madrid",
        "Barcelona",
        4000.0,
        4.0,
        2.5,
        16.0,
        "EURO_VI",
        None,
    )
    redis = _FakeRedis({rkey: json.dumps(payload)})

    async def _fake() -> _FakeRedis:
        return redis

    monkeypatch.setattr(ms, "_get_redis_client", _fake)
    monkeypatch.setattr(geo, "_get_redis_client", _fake)

    svc = MapsService(db=None, quota_service=None)
    out = await svc.get_truck_route(
        "Madrid",
        "Barcelona",
        weight=4000.0,
        height=4.0,
        width=2.5,
        length=16.0,
        emission_type="EURO_VI",
        tenant_empresa_id=None,
    )
    assert out["distancia_km"] == pytest.approx(100.0)
    assert out["vehicle_type"] == "HEAVY_TRUCK"


@pytest.mark.asyncio
async def test_geo_route_second_call_uses_redis_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.geo_service as geo

    redis = _FakeRedis()
    api_calls = {"count": 0}

    async def _fake_redis_client() -> _FakeRedis:
        return redis

    async def _fake_compute_routes_v2(
        self: GeoService, *, origin: str, destination: str, api_key: str  # noqa: ARG001
    ) -> tuple[float, int]:
        api_calls["count"] += 1
        return 621_000.0, 22_320

    monkeypatch.setattr(geo, "_get_redis_client", _fake_redis_client)
    monkeypatch.setattr(GeoService, "maps_api_key", staticmethod(lambda: "test-key"))
    monkeypatch.setattr(GeoService, "_compute_routes_v2", _fake_compute_routes_v2)

    svc = GeoService(db=None, quota_service=None)
    first = await svc.get_route_data("40.416775,-3.703790", "41.387400,2.168600")
    second = await svc.get_route_data("40.416775,-3.703790", "41.387400,2.168600")

    assert api_calls["count"] == 1
    assert first["distance_meters"] == second["distance_meters"] == 621000
    assert first["source"] == "api"
    assert second["source"] == "cache"
