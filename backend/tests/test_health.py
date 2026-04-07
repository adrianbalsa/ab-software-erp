from __future__ import annotations

import pytest


async def test_health_liveness_returns_plain_ok(client) -> None:
    """GET /health: fast-path middleware (sin TrustedHost estricto en prod)."""
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.text == "OK"
    assert res.headers.get("content-type", "").startswith("text/plain")


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
