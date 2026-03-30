from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _mock_supabase_rest_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita HTTP real a PostgREST en GET /health (tests sin red)."""

    async def _ok(_url: str, _key: str) -> tuple[bool, str]:
        return True, "supabase_ok"

    monkeypatch.setattr(
        "app.core.health_checks.check_supabase_rest",
        _ok,
    )


async def test_health_returns_ok_when_supabase_passes(client) -> None:
    res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["supabase"]["ok"] is True


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
