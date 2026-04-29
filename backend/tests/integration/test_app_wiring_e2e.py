from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt


class _FakeQuery:
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def ilike(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def not_(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def insert(self, *_args, **_kwargs):
        return self

    def update(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _FakeSupabaseDb:
    def table(self, _name: str) -> _FakeQuery:
        return _FakeQuery()

    async def execute(self, query):
        return query.execute()

    async def rpc(self, *_args, **_kwargs):
        return SimpleNamespace(data=[])


class _FakeRedisClient:
    def __init__(self) -> None:
        self._zsets: dict[str, list[float]] = {}

    async def ping(self):
        return True

    async def aclose(self):
        return None

    def pipeline(self, transaction: bool = True):  # noqa: ARG002
        client = self
        ops: list[tuple[str, tuple]] = []

        class _Pipe:
            def zremrangebyscore(self, key: str, _min: str, max_score: float):
                ops.append(("zremrangebyscore", (key, float(max_score))))
                return self

            def zadd(self, key: str, values: dict[str, float]):
                score = float(next(iter(values.values())))
                ops.append(("zadd", (key, score)))
                return self

            def zcard(self, key: str):
                ops.append(("zcard", (key,)))
                return self

            def expire(self, key: str, _ttl: int):
                ops.append(("expire", (key,)))
                return self

            async def execute(self):
                out: list[int] = []
                for op, args in ops:
                    if op == "zremrangebyscore":
                        key, max_score = args
                        rows = client._zsets.get(key, [])
                        client._zsets[key] = [s for s in rows if s > max_score]
                        out.append(0)
                    elif op == "zadd":
                        key, score = args
                        client._zsets.setdefault(key, []).append(score)
                        out.append(1)
                    elif op == "zcard":
                        key = args[0]
                        out.append(len(client._zsets.get(key, [])))
                    else:
                        out.append(1)
                return out

        return _Pipe()

    async def zrange(self, key: str, _start: int, _end: int, withscores: bool = False):
        rows = sorted(self._zsets.get(key, []))
        if not rows:
            return []
        if withscores:
            return [("member-1", rows[0])]
        return ["member-1"]


def _build_jwt(*, tenant_id: str) -> str:
    payload = {
        "sub": "e2e-user@ab-logistics.test",
        "empresa_id": tenant_id,
        "role": "authenticated",
        "app_role": "enterprise",
    }
    return jose_jwt.encode(payload, "unit-test-app-jwt-secret-32-characters!", algorithm="HS256")


@pytest.fixture
async def e2e_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-role-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-app-jwt-secret-32-characters!")
    monkeypatch.setenv("ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setenv("SESSION_SECRET_KEY", "unit-test-session-secret-32-characters")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.delenv("REDIS_URL", raising=False)

    from app.core.config import get_settings
    from app.core.rate_limit import get_rate_limit_storage_uri, get_rate_limit_strategy
    from app.main import create_app
    from app.models.enums import UserRole
    from app.schemas.user import UserOut
    from app.services.auth_service import AuthService

    fake_db = _FakeSupabaseDb()
    fake_redis = _FakeRedisClient()

    async def _fake_get_supabase(*_args, **_kwargs):
        return fake_db

    async def _fake_profile(_self, *, subject: str):  # noqa: ARG001
        return UserOut(
            username=subject,
            empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            role=UserRole.ADMIN,
            rol="admin",
            rbac_role="owner",
            cliente_id=None,
            assigned_vehiculo_id=None,
            usuario_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        )

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.db.supabase.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_k: fake_redis)
    monkeypatch.setattr(AuthService, "get_profile_by_subject", _fake_profile)
    monkeypatch.setattr(AuthService, "ensure_empresa_context", _noop)
    monkeypatch.setattr(AuthService, "ensure_rbac_context", _noop)

    get_settings.cache_clear()
    get_rate_limit_strategy.cache_clear()
    get_rate_limit_storage_uri.cache_clear()
    app = create_app()
    try:
        transport = ASGITransport(app=app, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_cors_integrity_allowed_and_disallowed_origins(e2e_client: AsyncClient) -> None:
    allowed_origin = "http://localhost:3000"
    denied_origin = "https://evil.example.com"
    token = _build_jwt(tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    ok = await e2e_client.options(
        "/api/v1/non-existing",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
            "Authorization": f"Bearer {token}",
        },
    )
    assert ok.status_code == 200
    assert ok.headers.get("access-control-allow-origin") == allowed_origin

    denied = await e2e_client.options(
        "/api/v1/non-existing",
        headers={
            "Origin": denied_origin,
            "Access-Control-Request-Method": "GET",
            "Authorization": f"Bearer {token}",
        },
    )
    assert denied.status_code in {400, 403}
    assert denied.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_bi_rate_limit_applies_per_tenant_before_general(e2e_client: AsyncClient) -> None:
    token = _build_jwt(tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(30):
        response = await e2e_client.get("/api/v1/bi/non-existing", headers=headers)
        assert response.status_code == 404

    blocked_bi = await e2e_client.get("/api/v1/bi/non-existing", headers=headers)
    assert blocked_bi.status_code == 429
    body = blocked_bi.json()
    assert body.get("bucket") == "bi"
    assert body.get("tenant_id") == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    # El límite general (100/min IP) debe seguir intacto cuando BI ya se agotó.
    general = await e2e_client.get("/api/v1/non-existing", headers=headers)
    assert general.status_code == 404


def test_dependency_injection_uses_testing_false_in_e2e() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.TESTING is False

