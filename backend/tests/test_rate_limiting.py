"""Políticas de rate limiting (global, auth, fiscal y buckets costosos)."""

from __future__ import annotations

import json

from httpx import ASGITransport, AsyncClient
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.rate_limit import (
    expensive_endpoint_bucket,
    fiscal_aeat_submission_path,
    get_rate_limit_strategy,
)
from app.middleware.rate_limit_middleware import (
    EndpointCostRateLimitMiddleware,
    TenantRateLimitMiddleware,
)
from app.services.usage_service import UsageService


def test_fiscal_aeat_paths_match_verifactu_and_facturas() -> None:
    assert fiscal_aeat_submission_path("/api/v1/verifactu/retry-pending", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/verifactu/audit/qr-preview/1", "GET") is False
    assert fiscal_aeat_submission_path("/api/v1/verifactu/dead-jobs", "GET") is False
    assert fiscal_aeat_submission_path("/api/v1/facturas/42/finalizar", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/facturas/42/reenviar-aeat", "POST") is True
    assert fiscal_aeat_submission_path("/facturas/1/finalizar", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/facturas/1/finalizar", "GET") is False


def test_expensive_endpoint_bucket_matching() -> None:
    assert expensive_endpoint_bucket("/ai/chat", "POST") == "ai"
    assert expensive_endpoint_bucket("/api/v1/advisor/ask", "POST") == "ai"
    assert expensive_endpoint_bucket("/api/v1/chatbot/ask", "POST") == "ai"
    assert expensive_endpoint_bucket("/maps/distance", "GET") == "maps"
    assert expensive_endpoint_bucket("/api/v1/routes/optimize-route", "POST") == "maps"
    assert expensive_endpoint_bucket("/gastos/ocr", "POST") == "ocr"
    assert expensive_endpoint_bucket("/api/v1/gastos/logistics-ticket", "POST") == "ocr"
    assert expensive_endpoint_bucket("/api/v1/verifactu/retry-pending", "POST") is None


@pytest.mark.asyncio
async def test_tenant_rate_limit_override_is_isolated_and_traceable(
    monkeypatch: pytest.MonkeyPatch,
    mock_user_empresa_a: dict[str, object],
    mock_user_empresa_b: dict[str, object],
) -> None:
    from app.core.config import get_settings

    async def ok(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    tenant_a = str(mock_user_empresa_a["empresa_id"])
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("TENANT_RATE_LIMIT_DEFAULT", "100 per minute")
    monkeypatch.setenv(
        "TENANT_RATE_LIMIT_OVERRIDES",
        json.dumps({tenant_a: "1 per minute"}),
    )
    get_settings.cache_clear()
    get_rate_limit_strategy.cache_clear()

    app = Starlette(routes=[Route("/api/v1/facturas", ok)])
    app.add_middleware(TenantRateLimitMiddleware)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = {
                "Authorization": f"Bearer {mock_user_empresa_a['jwt']}",
                "X-Request-ID": "bill-001-trace",
            }
            headers_b = {"Authorization": f"Bearer {mock_user_empresa_b['jwt']}"}

            first = await client.get("/api/v1/facturas", headers=headers_a)
            second = await client.get("/api/v1/facturas", headers=headers_a)
            other_tenant = await client.get("/api/v1/facturas", headers=headers_b)
    finally:
        get_rate_limit_strategy.cache_clear()
        get_settings.cache_clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert other_tenant.status_code == 200
    assert second.headers["x-request-id"] == "bill-001-trace"
    assert second.headers["retry-after"].isdigit()

    payload = second.json()
    assert payload["code"] == "rate_limit_exceeded"
    assert payload["request_id"] == "bill-001-trace"
    assert payload["tenant_id"] == tenant_a
    assert "Demasiadas solicitudes" in payload["message"]


@pytest.mark.asyncio
async def test_maps_bucket_rate_limit_isolated_per_tenant(
    monkeypatch: pytest.MonkeyPatch,
    mock_user_empresa_a: dict[str, object],
    mock_user_empresa_b: dict[str, object],
) -> None:
    """Bucket ``maps`` (p. ej. optimize-route): 429 en un tenant no bloquea al otro."""
    from app.core.config import get_settings
    from limits.storage.memory import MemoryStorage
    from limits.strategies import MovingWindowRateLimiter
    import app.middleware.rate_limit_middleware as rlm

    async def ok(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    monkeypatch.setenv("MAPS_RATE_LIMIT", "1 per minute")
    monkeypatch.setenv("DEV_MODE", "true")
    strategy = MovingWindowRateLimiter(MemoryStorage())
    monkeypatch.setattr(rlm, "get_rate_limit_strategy", lambda: strategy)
    get_settings.cache_clear()
    get_rate_limit_strategy.cache_clear()

    app = Starlette(
        routes=[Route("/maps/distance", ok, methods=["GET"])]
    )
    app.add_middleware(EndpointCostRateLimitMiddleware)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            ha = {"Authorization": f"Bearer {mock_user_empresa_a['jwt']}"}
            hb = {"Authorization": f"Bearer {mock_user_empresa_b['jwt']}"}
            a1 = await client.get("/maps/distance", headers=ha)
            a2 = await client.get("/maps/distance", headers=ha)
            b1 = await client.get("/maps/distance", headers=hb)
    finally:
        get_rate_limit_strategy.cache_clear()
        get_settings.cache_clear()

    assert a1.status_code == 200
    assert a2.status_code == 429
    assert b1.status_code == 200
    body = a2.json()
    assert body["code"] == "rate_limit_exceeded"
    assert body.get("bucket") == "maps"
    assert body["tenant_id"] == str(mock_user_empresa_a["empresa_id"])


@pytest.mark.asyncio
async def test_tenant_credit_bucket_blocks_when_balance_exhausted(
    mock_user_empresa_a: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ok(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    calls = {"n": 0}

    async def fake_check_credits(self, tenant_id: str, cost: int, *, plan: str = "starter") -> bool:
        _ = (self, tenant_id, cost, plan)
        calls["n"] += 1
        return calls["n"] == 1

    monkeypatch.setattr(UsageService, "check_credits", fake_check_credits)
    monkeypatch.setenv("DEV_MODE", "true")

    app = Starlette(
        routes=[Route("/maps/distance", ok, methods=["GET"])]
    )
    app.add_middleware(TenantRateLimitMiddleware)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {mock_user_empresa_a['jwt']}"}
        first = await client.get("/maps/distance", headers=headers)
        second = await client.get("/maps/distance", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Créditos insuficientes" in second.text
