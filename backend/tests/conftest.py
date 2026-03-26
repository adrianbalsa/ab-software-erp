from __future__ import annotations

import base64
import hashlib
import os
import sys
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient


def _install_stripe_test_double() -> None:
    """
    Evita importar/configurar el SDK real de Stripe en pytest.
    Debe ejecutarse antes de cargar ``app.main`` / ``stripe_pago`` (``import stripe``).
    """
    m = MagicMock(name="stripe_test_double")
    m.api_key = None

    SigErr = type("SignatureVerificationError", (Exception,), {})
    m.error = MagicMock()
    m.error.SignatureVerificationError = SigErr

    checkout_session = MagicMock()
    checkout_session.url = "https://checkout.stripe.test/mock-session"
    m.checkout = MagicMock()
    m.checkout.Session = MagicMock()
    m.checkout.Session.create = MagicMock(return_value=checkout_session)

    m.Webhook = MagicMock()
    m.Webhook.construct_event = MagicMock(
        return_value={"type": "checkout.session.completed", "data": {"object": {}}},
    )

    sys.modules["stripe"] = m


_install_stripe_test_double()

from app.core.security import create_access_token

# Tenants fijos para suites multi-tenant / JWT de prueba
EMPRESA_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EMPRESA_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture(autouse=True)
def _stripe_no_real_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Refuerzo por test: sin llamadas reales a Stripe (api_key + Session.create acotados).
    """
    import stripe as stripe_mod

    monkeypatch.setattr(stripe_mod, "api_key", "sk_test_stub_no_network", raising=False)
    sess = MagicMock()
    sess.url = "https://checkout.stripe.test/mock-session"
    create_mock = MagicMock(return_value=sess)
    if hasattr(stripe_mod, "checkout") and hasattr(stripe_mod.checkout, "Session"):
        monkeypatch.setattr(stripe_mod.checkout.Session, "create", create_mock, raising=False)


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Variables mínimas para ``get_settings()`` (sin tocar Supabase real)."""
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-role-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "unit-test-jwt-secret-at-least-32-chars")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-app-jwt-secret-32-characters!")
    # Fernet (44 chars) para cifrado en reposo (IBAN / suites que usen encryption)
    _fk = base64.urlsafe_b64encode(
        hashlib.sha256(b"abl-scanner-unit-test-fernet-v1").digest(),
    ).decode("ascii")
    monkeypatch.setenv("ENCRYPTION_KEY", _fk)
    monkeypatch.delenv("ENCRYPTION_SECRET_KEY", raising=False)
    monkeypatch.delenv("BANK_TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()


class _FakeQuery:
    """Cadena mínima compatible con ``SupabaseAsync.execute(query)`` (sync ``query.execute()``)."""

    def select(self, *args: object) -> _FakeQuery:
        return self

    def eq(self, *args: object) -> _FakeQuery:
        return self

    def ilike(self, *args: object) -> _FakeQuery:
        return self

    def insert(self, *args: object) -> _FakeQuery:
        return self

    def upsert(self, *args: object, **kwargs: object) -> _FakeQuery:
        return self

    def update(self, *args: object) -> _FakeQuery:
        return self

    def limit(self, *args: object) -> _FakeQuery:
        return self

    def order(self, *args: object) -> _FakeQuery:
        return self

    def is_(self, *args: object) -> _FakeQuery:
        return self

    def in_(self, *args: object) -> _FakeQuery:
        return self

    def not_(self) -> _FakeQuery:
        return self

    def execute(self) -> object:
        class _R:
            data: list = []

        return _R()


class _FakeSupabaseDb:
    """
    Subconjunto de ``SupabaseAsync``: ``table`` + ``execute`` (tests sin red).
    """

    def table(self, _name: str) -> _FakeQuery:
        return _FakeQuery()

    async def execute(self, query: object) -> object:
        return query.execute()

    async def rpc(self, *_a: object, **_k: object) -> None:
        return None

    async def storage_upload(self, **_k: object) -> None:
        return None

    async def storage_signed_url(self, **_k: object) -> None:
        return None

    @property
    def storage(self) -> object:
        return MagicMock()


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch):
    """``httpx.AsyncClient`` sobre la app ASGI con Supabase y health checks mockeados (sin red)."""
    from unittest.mock import AsyncMock

    from app.core.config import get_settings

    async def _fake_get_supabase(*_a: object, **_k: object) -> _FakeSupabaseDb:
        return _FakeSupabaseDb()

    # Cada módulo mantiene su referencia importada al importar; parchear todos
    monkeypatch.setattr("app.db.supabase.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.main.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.api.deps.get_supabase", _fake_get_supabase)

    monkeypatch.setattr(
        "app.core.health_checks.run_deep_health",
        AsyncMock(
            return_value={
                "status": "healthy",
                "checks": {
                    "supabase": {"ok": True, "detail": "supabase_ok"},
                    "finance_service": {"ok": True, "detail": "finance_ok"},
                },
            },
        ),
    )
    get_settings.cache_clear()

    os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")

    from app.main import create_app

    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_user_empresa_a() -> dict[str, object]:
    """JWT de app (HS256) + metadatos del tenant A."""
    token = create_access_token(
        subject="user_a@ab-logistics.test",
        empresa_id=str(EMPRESA_A_ID),
    )
    return {
        "jwt": token,
        "empresa_id": EMPRESA_A_ID,
        "sub": "user_a@ab-logistics.test",
    }


@pytest.fixture
def mock_user_empresa_b() -> dict[str, object]:
    """JWT de app (HS256) + metadatos del tenant B."""
    token = create_access_token(
        subject="user_b@ab-logistics.test",
        empresa_id=str(EMPRESA_B_ID),
    )
    return {
        "jwt": token,
        "empresa_id": EMPRESA_B_ID,
        "sub": "user_b@ab-logistics.test",
    }
