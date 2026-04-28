from __future__ import annotations

import pytest


class _FakeRedis:
    def __init__(self) -> None:
        self.values = {"stats:total_savings_euros": "1.5"}
        self.hashes = {"stats:routes_cache_metrics": {"hits": 6, "misses": 2}}

    async def get(self, key: str) -> str | None:
        value = self.values.get(key)
        return str(value) if value is not None else None

    async def hgetall(self, key: str) -> dict[str, int]:
        return dict(self.hashes.get(key, {}))


@pytest.mark.asyncio
async def test_check_geo_cache_economics_returns_savings_and_hit_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.health_checks as hc

    redis = _FakeRedis()

    async def _fake_get_redis_client() -> _FakeRedis:
        return redis

    monkeypatch.setattr("app.services.geo_service._get_redis_client", _fake_get_redis_client)

    out = await hc.check_geo_cache_economics()
    assert out["ok"] is True
    assert out["total_savings_euros"] == pytest.approx(1.5)
    assert out["hit_rate"] == pytest.approx(0.75)
    assert out["hits"] == pytest.approx(6.0)
    assert out["misses"] == pytest.approx(2.0)
