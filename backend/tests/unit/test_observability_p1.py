from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.middleware.critical_path_sentry import classify_p1_critical_route


def test_classify_p1_critical_routes() -> None:
    assert classify_p1_critical_route("POST", "/api/v1/verifactu/submit-final/abc") == "verifactu_submit_final"
    assert classify_p1_critical_route("POST", "/api/v1/advisor/ask") == "advisor_ask"
    assert classify_p1_critical_route("GET", "/health") == "health_readiness"
    assert classify_p1_critical_route("GET", "/api/v1/bi/financial-health") == "bi_financial_health"
    assert classify_p1_critical_route("GET", "/health/deep") is None
    assert classify_p1_critical_route("POST", "/api/v1/other") is None


@pytest.mark.asyncio
async def test_check_sentry_p1_configuration_fails_in_production_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ProdNoSentry:
        TESTING = False
        ENVIRONMENT = "production"
        SENTRY_DSN = ""

    monkeypatch.setattr("app.core.config.get_settings", lambda: _ProdNoSentry())
    get_settings.cache_clear()
    from app.core.observability_p1 import check_sentry_p1_configuration

    try:
        out = await check_sentry_p1_configuration()
    finally:
        get_settings.cache_clear()

    assert out["ok"] is False
    assert out.get("skipped") is False
    assert "sentry" in (out.get("detail") or "").lower()
