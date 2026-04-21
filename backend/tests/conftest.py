from __future__ import annotations

import base64
import hashlib
import json
import os
import sys

# Antes de que los tests importen módulos que instancian SlowAPI en import-time
# (p. ej. ``app.core.rate_limit``), sin depender del fixture ``_test_env``.
os.environ.setdefault("DEV_MODE", "true")
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt


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


def _install_weasyprint_test_double() -> None:
    """
    ``app.api.deps`` arrastra ``facturas_service`` → ``report_service`` → ``weasyprint`` (GTK/Pango).
    En runners sin esas libs, registrar un stub evita errores de import en colección/ejecución.
    """
    m = MagicMock(name="weasyprint_test_double")
    m.HTML = MagicMock()
    sys.modules.setdefault("weasyprint", m)


_install_weasyprint_test_double()

from app.core.security import create_access_token

# Tenants fijos para suites multi-tenant / JWT de prueba
EMPRESA_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EMPRESA_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# Identidad por defecto del fixture ``client`` (perfil semilla + ``sub`` JWT tipo Supabase UUID).
TEST_CLIENT_SUBJECT = "ci-enterprise-owner@ab-logistics.test"
TEST_PROFILE_USER_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
TEST_CLIENT_JWT_SUB = str(TEST_PROFILE_USER_ID)


def _resolve_seed_empresa_id() -> UUID:
    """
    ``admin_empresa_id`` de ``tests/.smoke_seed_ids.json`` (tras ``seed_test_data``),
    o ``EMPRESA_A_ID`` si no hay fichero.
    """
    here = Path(__file__).resolve()
    candidates = (
        here.parent / ".smoke_seed_ids.json",
        here.parent.parent.parent / "tests" / ".smoke_seed_ids.json",
    )
    for p in candidates:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            raw = str(data.get("admin_empresa_id") or "").strip()
            if raw:
                return UUID(raw)
        except Exception:
            continue
    return EMPRESA_A_ID


def _build_default_test_api_jwt(*, empresa_id: UUID) -> str:
    """JWT HS256 de la API con los claims que exige ``get_current_user`` + middleware RLS."""
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=2)
    payload: dict[str, Any] = {
        "sub": TEST_CLIENT_JWT_SUB,
        "role": "authenticated",
        "app_role": "enterprise",
        "empresa_id": str(empresa_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def _resend_emails_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Evita llamadas HTTP reales a Resend cuando los tests ejecutan ``BackgroundTasks``
    (p. ej. reenvío de invitación o PDF de factura).
    """
    from unittest.mock import MagicMock

    fake_emails = MagicMock()
    fake_emails.send = MagicMock(return_value={"id": "test-resend-stub"})
    fake_resend = MagicMock()
    fake_resend.Emails = fake_emails
    fake_resend.api_key = None
    monkeypatch.setattr("app.services.email_service.resend", fake_resend, raising=True)


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
    # Stripe webhooks (``handle_webhook``) leen el secreto vía ``get_secret_manager()``;
    # en CI no hay signing secret real — dummy estable para idempotencia / construct_event mockeado.
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_dummy_test_secret")
    # Alineado con CI (`.github/workflows/deploy.yml`): SlowAPI sin Redis en tests.
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    from app.core.config import get_settings
    from app.services.secret_manager_service import reset_secret_manager

    get_settings.cache_clear()
    reset_secret_manager()


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

    Conserva el JWT inyectado por ``get_supabase(jwt_token=…)`` (misma identidad que PostgREST/RLS).
    """

    def __init__(self, jwt_token: str | None = None) -> None:
        t = str(jwt_token).strip() if jwt_token is not None else ""
        self._jwt_token: str | None = t if t else None
        self._jwt_claims: dict[str, Any] | None = None

    @property
    def jwt_token(self) -> str | None:
        return self._jwt_token

    @property
    def jwt_claims(self) -> dict[str, Any]:
        if self._jwt_claims is None:
            self._jwt_claims = {}
            if self._jwt_token:
                from app.core.security import decode_access_token_payload

                try:
                    self._jwt_claims = decode_access_token_payload(self._jwt_token)
                except ValueError:
                    self._jwt_claims = {}
        return self._jwt_claims

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
    from app.models.enums import UserRole
    from app.schemas.user import UserOut
    from app.services.auth_service import AuthService

    seed_empresa_id = _resolve_seed_empresa_id()
    default_bearer = _build_default_test_api_jwt(empresa_id=seed_empresa_id)

    async def _fake_get_supabase(
        *_a: object,
        jwt_token: str | None = None,
        **_k: object,
    ) -> _FakeSupabaseDb:
        return _FakeSupabaseDb(jwt_token=jwt_token)

    def _profile_for_subject(subject: str) -> UserOut | None:
        s = (subject or "").strip()
        if s in (TEST_CLIENT_JWT_SUB, TEST_CLIENT_SUBJECT):
            # JWT puede llevar ``sub`` = profiles.id; ``app_role=enterprise`` es slug de plan
            # (``get_current_user`` no lo cruza con el rol operativo del perfil).
            return UserOut(
                username=TEST_CLIENT_SUBJECT,
                empresa_id=seed_empresa_id,
                role=UserRole.ADMIN,
                rol="admin",
                rbac_role="owner",
                cliente_id=None,
                assigned_vehiculo_id=None,
                usuario_id=TEST_PROFILE_USER_ID,
            )
        if s == "admin@qa.local":
            # ``tests/e2e/test_onboarding_to_porte_flow`` (Bearer distinto al usuario semilla CI).
            return UserOut(
                username=s,
                empresa_id=EMPRESA_A_ID,
                role=UserRole.ADMIN,
                rol="admin",
                rbac_role="traffic_manager",
                cliente_id=None,
                assigned_vehiculo_id=None,
                usuario_id=UUID("99999999-9999-9999-9999-999999999999"),
            )
        # JWT de ``mock_user_empresa_a`` / ``mock_user_empresa_b`` (suites multi-tenant).
        if s == "user_a@ab-logistics.test":
            return UserOut(
                username=s,
                empresa_id=EMPRESA_A_ID,
                role=UserRole.GESTOR,
                rol="user",
                rbac_role="owner",
                cliente_id=None,
                assigned_vehiculo_id=None,
                usuario_id=None,
            )
        if s == "user_b@ab-logistics.test":
            return UserOut(
                username=s,
                empresa_id=EMPRESA_B_ID,
                role=UserRole.GESTOR,
                rol="user",
                rbac_role="owner",
                cliente_id=None,
                assigned_vehiculo_id=None,
                usuario_id=None,
            )
        return None

    async def _stub_get_profile_by_subject(self: AuthService, *, subject: str) -> UserOut | None:
        return _profile_for_subject(subject)

    monkeypatch.setattr(AuthService, "get_profile_by_subject", _stub_get_profile_by_subject)

    # ``deps`` usa ``supabase_db.get_supabase``; middleware importa el símbolo localmente.
    monkeypatch.setattr("app.db.supabase.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _fake_get_supabase)

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
    from app.services.secret_manager_service import reset_secret_manager

    get_settings.cache_clear()
    reset_secret_manager()

    os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")

    from app.main import create_app

    application = create_app()
    # httpx 0.28+: lifespan="on" ejecuta startup/shutdown de FastAPI en tests.
    try:
        transport = ASGITransport(app=application, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=application)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {default_bearer}"},
    ) as ac:
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
