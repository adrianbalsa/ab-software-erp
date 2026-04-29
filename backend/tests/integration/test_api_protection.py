from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt
from fastapi import FastAPI

from app.core.config import get_settings
from app.middleware.fiscal_rate_limit_middleware import FiscalVerifactuRateLimitMiddleware
from app.middleware.rate_limit_middleware import BIRateLimitMiddleware, GlobalIPRateLimitMiddleware
from app.openapi_config import attach_custom_openapi


def _reset_rate_limit_runtime_state() -> None:
    from app.core.rate_limit import get_rate_limit_storage_uri, get_rate_limit_strategy

    get_settings.cache_clear()
    get_rate_limit_strategy.cache_clear()
    get_rate_limit_storage_uri.cache_clear()


def _build_test_jwt() -> str:
    secret = "unit-test-app-jwt-secret-32-characters!"
    payload = {
        "sub": "qa-protection-user",
        "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "role": "authenticated",
        "app_role": "enterprise",
    }
    return jose_jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
async def protection_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-role-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-app-jwt-secret-32-characters!")
    monkeypatch.setenv("ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setenv("SESSION_SECRET_KEY", "unit-test-session-secret-32-characters")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("TESTING", "false")

    _reset_rate_limit_runtime_state()

    application = FastAPI(
        title="Protection Test API",
        openapi_url="/api/v1/openapi.json",
    )
    attach_custom_openapi(application)
    application.add_middleware(GlobalIPRateLimitMiddleware)
    application.add_middleware(BIRateLimitMiddleware)
    application.add_middleware(FiscalVerifactuRateLimitMiddleware)

    @application.post("/api/v1/verifactu/retry-pending")
    async def fiscal_ok() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/v1/bi/dashboard/summary")
    async def bi_ok() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/v1/general/ping")
    async def general_ok() -> dict[str, bool]:
        return {"ok": True}

    token = _build_test_jwt()
    try:
        transport = ASGITransport(app=application, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=application)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_verifactu_bypass_with_testing_true(protection_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTING", "true")
    _reset_rate_limit_runtime_state()

    for _ in range(15):
        response = await protection_client.post("/api/v1/verifactu/retry-pending")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_fiscal_blocks_after_10_requests_when_testing_false(
    protection_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TESTING", "false")
    _reset_rate_limit_runtime_state()

    for _ in range(10):
        response = await protection_client.post("/api/v1/verifactu/retry-pending")
        assert response.status_code == 200

    blocked = await protection_client.post("/api/v1/verifactu/retry-pending")
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")
    payload = blocked.json()
    assert "retry_after" in payload


@pytest.mark.asyncio
async def test_bi_rate_limit_is_independent_from_general_limit(
    protection_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TESTING", "false")
    _reset_rate_limit_runtime_state()

    # Consume el bucket general (100/min por IP) en una ruta no BI/no fiscal.
    for _ in range(100):
        response = await protection_client.get("/api/v1/general/ping")
        assert response.status_code == 200

    blocked_general = await protection_client.get("/api/v1/general/ping")
    assert blocked_general.status_code == 429

    # BI tiene su propio bucket (30/min), por lo que debe empezar sin bloqueo.
    first_bi = await protection_client.get("/api/v1/bi/dashboard/summary")
    assert first_bi.status_code == 200

    for _ in range(29):
        response = await protection_client.get("/api/v1/bi/dashboard/summary")
        assert response.status_code == 200

    blocked_bi = await protection_client.get("/api/v1/bi/dashboard/summary")
    assert blocked_bi.status_code == 429


@pytest.mark.asyncio
async def test_openapi_includes_429_for_bi_and_fiscal(protection_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTING", "false")
    _reset_rate_limit_runtime_state()

    openapi = await protection_client.get("/api/v1/openapi.json")
    assert openapi.status_code == 200
    spec = openapi.json()
    paths = spec.get("paths", {})

    bi_ops = paths.get("/api/v1/bi/dashboard/summary", {})
    assert "429" in bi_ops.get("get", {}).get("responses", {})

    fiscal_ops = paths.get("/api/v1/verifactu/retry-pending", {})
    assert "429" in fiscal_ops.get("post", {}).get("responses", {})

