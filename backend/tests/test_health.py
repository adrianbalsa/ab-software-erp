from __future__ import annotations

import pytest


async def test_live_liveness_returns_ok(client) -> None:
    """GET /live: bypass antes de TrustedHost (Railway / balanceadores)."""
    res = await client.get("/live")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body.get("request_id")
    assert res.headers.get("x-request-id") == body["request_id"]


async def test_live_propagates_incoming_request_id(client) -> None:
    res = await client.get("/live", headers={"X-Request-ID": "probe-abc-123"})
    assert res.status_code == 200
    assert res.headers.get("x-request-id") == "probe-abc-123"
    assert res.json()["request_id"] == "probe-abc-123"


async def test_health_readiness_returns_healthy_when_dependencies_ok(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _sup_ok(*_a: object, **_k: object) -> tuple[bool, str]:
        return True, "supabase_ok"

    async def _redis_ok() -> dict[str, object]:
        return {"ok": True, "detail": "redis_ping_ok", "skipped": False}

    monkeypatch.setattr("app.core.health_checks.check_supabase_rest", _sup_ok)
    monkeypatch.setattr("app.core.health_checks.check_redis_ping", _redis_ok)

    res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["checks"]["supabase"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True
    assert body.get("request_id")


async def test_health_deep_returns_healthy_when_checks_pass(client) -> None:
    res = await client.get("/health/deep")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["checks"]["supabase"]["ok"] is True
    assert body["checks"]["finance_service"]["ok"] is True


async def test_ready_is_always_ok(client) -> None:
    res = await client.get("/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
