from __future__ import annotations

import time
from collections import deque
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.core.config import get_settings
from app.core.rate_limit import get_rate_limit_storage_uri, get_rate_limit_strategy
from app.main import create_app


class _FakeQuery:
    def select(self, *_args: object, **_kwargs: object) -> "_FakeQuery":
        return self

    def eq(self, *_args: object, **_kwargs: object) -> "_FakeQuery":
        return self

    def order(self, *_args: object, **_kwargs: object) -> "_FakeQuery":
        return self

    def limit(self, *_args: object, **_kwargs: object) -> "_FakeQuery":
        return self

    def execute(self) -> object:
        class _R:
            data: list[dict[str, object]] = []

        return _R()


class _FakeSupabaseDb:
    def table(self, _name: str) -> _FakeQuery:
        return _FakeQuery()

    async def execute(self, query: object) -> object:
        return query.execute()


class _FakeRedisPipeline:
    def zremrangebyscore(self, *_args: object, **_kwargs: object) -> "_FakeRedisPipeline":
        return self

    def zadd(self, *_args: object, **_kwargs: object) -> "_FakeRedisPipeline":
        return self

    def zcard(self, *_args: object, **_kwargs: object) -> "_FakeRedisPipeline":
        return self

    def expire(self, *_args: object, **_kwargs: object) -> "_FakeRedisPipeline":
        return self

    async def execute(self) -> list[object]:
        return [None, None, 1, None]


class _FakeRedisClient:
    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    def pipeline(self, **_kwargs: object) -> _FakeRedisPipeline:
        return _FakeRedisPipeline()

    async def zrange(self, *_args: object, **_kwargs: object) -> list[tuple[str, float]]:
        return [("member", time.time())]


def _clear_runtime_caches() -> None:
    get_settings.cache_clear()
    get_rate_limit_strategy.cache_clear()
    get_rate_limit_storage_uri.cache_clear()


def _build_jwt(empresa_id: str) -> str:
    payload = {
        "sub": "qa-app-wiring-user",
        "empresa_id": empresa_id,
        "role": "authenticated",
        "app_role": "enterprise",
    }
    return jose_jwt.encode(payload, "unit-test-app-jwt-secret-32-characters!", algorithm="HS256")


def _auth_headers(empresa_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") -> dict[str, str]:
    return {"Authorization": f"Bearer {_build_jwt(empresa_id)}"}


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-role-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-app-jwt-secret-32-characters!")
    monkeypatch.setenv("ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setenv("SESSION_SECRET_KEY", "unit-test-session-secret-32-characters")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://frontend.example.com")
    monkeypatch.delenv("REDIS_URL", raising=False)

    _clear_runtime_caches()

    async def _fake_get_supabase(*_args: object, **_kwargs: object) -> _FakeSupabaseDb:
        return _FakeSupabaseDb()

    monkeypatch.setattr("app.db.supabase.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: _FakeRedisClient())

    async def _stub_get_profile_by_subject(self: Any, *, subject: str) -> Any:
        return type("UserStub", (), {"empresa_id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")})()

    async def _noop_async(self: Any, *args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.services.auth_service.AuthService.get_profile_by_subject", _stub_get_profile_by_subject)
    monkeypatch.setattr("app.services.auth_service.AuthService.ensure_empresa_context", _noop_async)
    monkeypatch.setattr("app.services.auth_service.AuthService.ensure_rbac_context", _noop_async)
    original_httpx_client_init = httpx.Client.__init__

    def _httpx_client_init_compat(self: httpx.Client, *args: object, **kwargs: object) -> None:
        kwargs.pop("app", None)
        original_httpx_client_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", _httpx_client_init_compat)

    app = create_app()
    with TestClient(app) as client:
        yield client


def test_cors_headers_are_applied(app_client: TestClient) -> None:
    response = app_client.options(
        "/api/v1/bi/dashboard/summary",
        headers={
            "Origin": "https://frontend.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
            **_auth_headers(),
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "https://frontend.example.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_auth_identity_is_used_by_bi_rate_limit(app_client: TestClient) -> None:
    headers = _auth_headers("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    statuses = deque(maxlen=3)

    for _ in range(30):
        response = app_client.get("/api/v1/bi/dashboard/summary", headers=headers)
        statuses.append(response.status_code)

    blocked = app_client.get("/api/v1/bi/dashboard/summary", headers=headers)

    assert 429 not in statuses
    assert blocked.status_code == 429
    payload = blocked.json()
    assert payload.get("tenant_id") == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert payload.get("scope") == "tenant"
    assert payload.get("limit") == "30 per 1 minute"


def test_testing_false_keeps_rate_limit_protections_enabled(app_client: TestClient) -> None:
    assert get_settings().TESTING is False

    headers = _auth_headers("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    for _ in range(30):
        app_client.get("/api/v1/bi/dashboard/summary", headers=headers)

    blocked = app_client.get("/api/v1/bi/dashboard/summary", headers=headers)
    assert blocked.status_code == 429


def test_openapi_v1_alias_and_security_scheme(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/openapi.json", headers=_auth_headers())
    assert response.status_code == 200

    schema = response.json()
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    assert "BearerAuth" in security_schemes
    assert security_schemes["BearerAuth"].get("scheme") == "bearer"

    bi_get = schema.get("paths", {}).get("/api/v1/bi/dashboard/summary", {}).get("get", {})
    responses = bi_get.get("responses", {})
    assert "429" in responses


def test_openapi_global_and_v1_alias_are_healthy(app_client: TestClient) -> None:
    root = app_client.get("/openapi.json", headers=_auth_headers())
    v1 = app_client.get("/api/v1/openapi.json", headers=_auth_headers())

    assert root.status_code == 200
    assert v1.status_code == 200

    root_schema = root.json()
    v1_schema = v1.json()

    assert root_schema.get("openapi")
    assert v1_schema.get("openapi")
    assert isinstance(root_schema.get("paths"), dict) and root_schema["paths"]
    assert isinstance(v1_schema.get("paths"), dict) and v1_schema["paths"]
    assert "/api/v1/bi/dashboard/summary" in root_schema["paths"]
    assert "/api/v1/bi/dashboard/summary" in v1_schema["paths"]
