"""
E2E (integración API) — Autonomous Onboarding.

Simula un usuario recién registrado en Supabase Auth:
- JWT de la API sin ``empresa_id`` (equivalente a "sin tenant" hasta completar onboarding).
- ``POST /auth/onboarding/setup`` crea empresa y enlaza perfil (RPC ``auth_onboarding_setup``).
- Verifica porte + IA para admin, y 409 en segundo onboarding.

Nota: la suite del repo usa ``httpx.AsyncClient`` + ASGI (sin Playwright); el escenario es el mismo
contrato HTTP que cubriría un test de UI.
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

sys.modules.setdefault("rapidfuzz", MagicMock(name="rapidfuzz_test_double"))
sys.modules.setdefault("litellm", MagicMock(name="litellm_test_double"))
sys.modules.setdefault("anthropic", MagicMock(name="anthropic_test_double"))

from app.api import deps
from app.core.security import create_access_token


# --- Identidades fijas (JWT sub = profiles.id, como Supabase Auth) -----------------
PROFILE_ID = UUID("aaaaaaaa-0001-0001-0001-000000000001")
CLIENTE_ID = UUID("bbbbbbbb-0001-0001-0001-000000000001")


class _ExecResult:
    __slots__ = ("data",)

    def __init__(self, data: list[dict[str, Any]] | None) -> None:
        self.data = data or []


class _FakeQuery:
    """Cadena PostgREST mínima: select/insert + eq + is_(null) + limit."""

    def __init__(self, fake: "OnboardingFakeSupabase", table: str) -> None:
        self._fake = fake
        self._table = table
        self._op = "select"
        self._cols = "*"
        self._filters: dict[str, Any] = {}
        self._null_if_missing: set[str] = set()
        self._payload: dict[str, Any] | None = None

    def select(self, cols: str = "*") -> _FakeQuery:
        self._cols = cols
        self._op = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeQuery:
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> _FakeQuery:
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self._filters[key] = value
        return self

    def is_(self, key: str, value: Any) -> _FakeQuery:
        if value == "null":
            self._null_if_missing.add(key)
        return self

    def order(self, *_a: object, **_k: object) -> _FakeQuery:
        return self

    def limit(self, *_a: object) -> _FakeQuery:
        return self

    def execute(self) -> _ExecResult:
        return self._fake._execute_table_query(self)


class OnboardingFakeSupabase:
    """
    Estado en memoria: ``profiles``, ``empresas``, ``clientes``, ``portes``, ``facturas``.
    RPC ``auth_onboarding_setup`` replica el contrato esperado por ``POST /auth/onboarding/setup``.
    """

    def __init__(self) -> None:
        self.profile_id = PROFILE_ID
        self.profiles: dict[str, dict[str, Any]] = {
            str(PROFILE_ID): {
                "id": str(PROFILE_ID),
                "username": "new.user@qa.ablogistics.test",
                "email": "new.user@qa.ablogistics.test",
                "empresa_id": None,
                "role": "owner",
                "rol": "user",
                "cliente_id": None,
                "assigned_vehiculo_id": None,
            }
        }
        self.empresas: dict[str, dict[str, Any]] = {}
        self.clientes: dict[str, dict[str, Any]] = {}
        self.portes: list[dict[str, Any]] = []
        self.facturas: list[dict[str, Any]] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)

    async def execute(self, query: object) -> _ExecResult:
        if hasattr(query, "execute"):
            return query.execute()
        raise TypeError("query must provide execute()")

    async def rpc(self, fn: str, params: dict[str, Any] | None = None) -> _ExecResult:
        p = params or {}
        if fn == "set_empresa_context":
            return _ExecResult([])
        if fn == "set_rbac_session":
            return _ExecResult([])
        if fn == "auth_onboarding_setup":
            return self._rpc_auth_onboarding_setup(p)
        return _ExecResult([])

    def _rpc_auth_onboarding_setup(self, p: dict[str, Any]) -> _ExecResult:
        pid = str(self.profile_id)
        row = self.profiles.get(pid)
        if not row:
            raise RuntimeError("profile_not_found")
        if row.get("empresa_id"):
            raise RuntimeError("already_onboarded")

        eid = str(uuid4())
        self.empresas[eid] = {
            "id": eid,
            "nif": p.get("p_cif"),
            "nombre_legal": p.get("p_company_name"),
            "nombre_comercial": p.get("p_company_name"),
            "direccion": p.get("p_address"),
            "plan": "starter",
            "plan_type": "starter",
            "activa": True,
            "deleted_at": None,
        }
        row["empresa_id"] = eid
        row["role"] = "admin"
        row["rol"] = "admin"

        self.clientes[str(CLIENTE_ID)] = {
            "id": str(CLIENTE_ID),
            "empresa_id": eid,
            "riesgo_aceptado": True,
            "limite_credito": 1_000_000.0,
            "deleted_at": None,
        }

        return _ExecResult(
            [
                {
                    "empresa_id": eid,
                    "profile_id": pid,
                    "role": "admin",
                }
            ]
        )

    def _execute_table_query(self, q: _FakeQuery) -> _ExecResult:
        t = q._table
        if t == "profiles" and q._op == "select":
            return self._select_profiles(q)
        if t == "empresas" and q._op == "select":
            eid = str(q._filters.get("id") or "")
            row = self.empresas.get(eid)
            return _ExecResult([dict(row)] if row else [])
        if t == "clientes" and q._op == "select":
            return self._select_clientes(q)
        if t == "facturas" and q._op == "select":
            eid = str(q._filters.get("empresa_id") or "")
            rows = [r for r in self.facturas if str(r.get("empresa_id")) == eid]
            return _ExecResult(rows)
        if t == "portes" and q._op == "select":
            return self._select_portes(q)
        if t == "portes" and q._op == "insert":
            assert q._payload is not None
            ins = dict(q._payload)
            ins.setdefault("id", str(uuid4()))
            self.portes.append(ins)
            return _ExecResult([ins])
        if t == "flota" and q._op == "select":
            return _ExecResult([])
        if t == "portes_activos" and q._op == "select":
            return _ExecResult([])
        return _ExecResult([])

    def _select_profiles(self, q: _FakeQuery) -> _ExecResult:
        if "id" in q._filters:
            r = self.profiles.get(str(q._filters["id"]))
            return _ExecResult([dict(r)] if r else [])
        for key in ("username", "email"):
            if key in q._filters:
                val = str(q._filters[key])
                for r in self.profiles.values():
                    if str(r.get(key) or "") == val:
                        return _ExecResult([dict(r)])
                return _ExecResult([])
        return _ExecResult([])

    def _select_clientes(self, q: _FakeQuery) -> _ExecResult:
        cid = str(q._filters.get("id") or "")
        eid = str(q._filters.get("empresa_id") or "")
        row = self.clientes.get(cid)
        if not row or (eid and str(row.get("empresa_id")) != eid):
            return _ExecResult([])
        if "deleted_at" in q._null_if_missing and row.get("deleted_at") is not None:
            return _ExecResult([])
        return _ExecResult([dict(row)])

    def _select_portes(self, q: _FakeQuery) -> _ExecResult:
        eid = str(q._filters.get("empresa_id") or "")
        rows = [r for r in self.portes if str(r.get("empresa_id")) == eid]
        if "deleted_at" in q._null_if_missing:
            rows = [r for r in rows if r.get("deleted_at") is None]
        return _ExecResult([dict(r) for r in rows])

    @property
    def storage(self) -> object:
        return MagicMock()


class _ConsultServiceStub:
    """Sustituye LogisAdvisorService en /ai/consult: sin LLM real (solo valida RBAC + tenant)."""

    @staticmethod
    def openai_configured() -> bool:
        return True

    async def build_data_context(self, *, empresa_id: str) -> dict[str, Any]:
        assert str(empresa_id).strip()
        return {
            "current_portes": [],
            "financial_summary": {},
            "maps_data": {},
        }

    async def generate_diagnostic(
        self,
        *,
        data_context: dict[str, Any],
        user_query: str,
    ) -> dict[str, Any]:
        _ = (data_context, user_query)
        return {
            "summary_headline": "OK QA",
            "profitability": {"status": "ok", "findings": [], "actions": []},
            "fiscal_safety": {"status": "ok", "findings": [], "actions": []},
            "liquidity": {"status": "ok", "findings": [], "actions": []},
            "risk_flags": [],
            "recommended_actions": [],
            "model": "e2e-stub",
        }


@pytest.fixture
async def onboarding_client(monkeypatch: pytest.MonkeyPatch):
    """AsyncClient ASGI + fake Supabase de onboarding (sin red)."""
    from unittest.mock import AsyncMock

    fake_db = OnboardingFakeSupabase()

    async def _fake_get_supabase(*_a: object, **_k: object) -> OnboardingFakeSupabase:
        return fake_db

    monkeypatch.setattr("app.db.supabase.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.api.deps.get_supabase", _fake_get_supabase)
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

    async def _fake_maps(_db: Any = None) -> object:
        class _M:
            async def get_distance_km(self, *_a: object, **_k: object) -> float:
                return 120.0

        return _M()

    monkeypatch.setattr("app.api.deps.get_maps_service", _fake_maps)

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    application = create_app()
    try:
        transport = ASGITransport(app=application, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, fake_db


@pytest.mark.asyncio
async def test_e2e_autonomous_onboarding_porte_ai_and_idempotency(
    onboarding_client: tuple[AsyncClient, OnboardingFakeSupabase],
) -> None:
    client, fake = onboarding_client

    # JWT "nuevo usuario": sin empresa_id ni role en claims (perfil aún sin tenant).
    token = create_access_token(
        subject=str(PROFILE_ID),
        empresa_id=None,
        role=None,
        rbac_role=None,
    )
    headers = {"Authorization": f"Bearer {token}"}

    setup_payload = {
        "company_name": "Transportes QA S.L.",
        "cif": "B12345678",
        "address": "Calle del Transporte 42, Madrid",
        "initial_fleet_type": "Articulado > 40t, Rígido 12-24t",
        "target_margin_pct": 18.5,
    }

    res_setup = await client.post("/auth/onboarding/setup", json=setup_payload, headers=headers)
    assert res_setup.status_code == 200, res_setup.text
    body_setup = res_setup.json()
    empresa_id = body_setup["empresa_id"]
    assert body_setup["role"] == "admin"
    assert UUID(str(empresa_id))

    prof = fake.profiles[str(PROFILE_ID)]
    assert prof["empresa_id"] == empresa_id
    assert str(prof.get("role", "")).lower() == "admin"

    porte_payload = {
        "cliente_id": str(CLIENTE_ID),
        "fecha": date.today().isoformat(),
        "origen": "Madrid",
        "destino": "Barcelona",
        "km_estimados": 620.0,
        "bultos": 12,
        "descripcion": "E2E onboarding",
        "precio_pactado": 1500.0,
    }
    res_porte = await client.post("/api/v1/portes/", json=porte_payload, headers=headers)
    assert res_porte.status_code == 201, res_porte.text
    assert res_porte.json().get("empresa_id") == empresa_id

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_logis_advisor_service] = lambda: _ConsultServiceStub()

    try:
        res_ai = await client.post("/ai/consult", json={"query": "Diagnóstico post-onboarding"}, headers=headers)
        assert res_ai.status_code == 200, res_ai.text
        assert res_ai.json().get("summary_headline") == "OK QA"
    finally:
        app.dependency_overrides.clear()

    res_dup = await client.post("/auth/onboarding/setup", json=setup_payload, headers=headers)
    assert res_dup.status_code == 409
    assert "empresa" in str(res_dup.json().get("detail", "")).lower()
