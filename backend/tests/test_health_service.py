from __future__ import annotations

import pytest

from app.services.health_service import perform_full_health_check, sanitize_error_message


def test_sanitize_error_message_strips_pg_password() -> None:
    raw = "fail: postgresql://appuser:SuperSecret123@db.internal:5432/prod"
    out = sanitize_error_message(raw)
    assert "SuperSecret123" not in out
    assert "***" in out


def test_sanitize_error_message_strips_password_param() -> None:
    raw = "error password=hunter2 in connection"
    out = sanitize_error_message(raw)
    assert "hunter2" not in out


@pytest.mark.asyncio
async def test_perform_full_health_check_skipped_without_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.health_service.get_engine", lambda: None)

    body = await perform_full_health_check()
    assert body["status"] == "skipped"
    assert body["database"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_health_status_endpoint_skipped(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.health_service.get_engine", lambda: None)
    res = await client.get("/health/status")
    assert res.status_code == 200
    assert res.json()["status"] == "skipped"
