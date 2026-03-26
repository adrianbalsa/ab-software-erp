from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.api import deps
from app.core.security import create_access_token
from app.schemas.user import UserOut
from app.services.maps_service import MapsService


@dataclass
class _FakeResult:
    data: list[dict[str, Any]] | None = None


class _FakeQuery:
    def __init__(self, table: str, action: str = "select", payload: dict[str, Any] | None = None) -> None:
        self.table = table
        self.action = action
        self.payload = payload or {}
        self.filters: dict[str, Any] = {}

    def select(self, *_args: object) -> _FakeQuery:
        self.action = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "insert"
        self.payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def is_(self, *_args: object) -> _FakeQuery:
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self


class _FakeDb:
    def __init__(self, *, empresa_id: str, cliente_id: str, cliente_email: str) -> None:
        self.empresa_id = empresa_id
        self.cliente_id = cliente_id
        self.invites_sent: list[str] = []
        self.audit_logs: list[dict[str, Any]] = []
        self.portes: list[dict[str, Any]] = []
        self.clientes: dict[str, dict[str, Any]] = {
            cliente_id: {
                "id": cliente_id,
                "empresa_id": empresa_id,
                "nombre": "Cliente Demo",
                "email": cliente_email,
                "riesgo_aceptado": False,
                "riesgo_aceptado_at": None,
                "limite_credito": 3500,
                "has_payment_history": False,
                "deleted_at": None,
            }
        }
        self.profiles: list[dict[str, Any]] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.table == "clientes":
            return self._exec_clientes(query)
        if query.table == "profiles":
            return self._exec_profiles(query)
        if query.table == "audit_logs" and query.action == "insert":
            self.audit_logs.append(dict(query.payload))
            return _FakeResult(data=[query.payload])
        if query.table == "portes" and query.action == "insert":
            row = {"id": str(uuid4()), **query.payload}
            self.portes.append(row)
            return _FakeResult(data=[row])
        return _FakeResult(data=[])

    async def auth_admin_invite_user_by_email(
        self,
        *,
        email: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.invites_sent.append(email)
        return {"user": {"email": email, "options": options or {}}}

    def _exec_clientes(self, query: _FakeQuery) -> _FakeResult:
        cid = str(query.filters.get("id") or "")
        eid = str(query.filters.get("empresa_id") or "")
        row = self.clientes.get(cid)
        if row is None or (eid and str(row.get("empresa_id")) != eid):
            return _FakeResult(data=[])

        if query.action == "select":
            return _FakeResult(data=[dict(row)])
        if query.action == "update":
            row.update(query.payload)
            return _FakeResult(data=[dict(row)])
        return _FakeResult(data=[])

    def _exec_profiles(self, query: _FakeQuery) -> _FakeResult:
        if query.action != "select":
            return _FakeResult(data=[])
        cid = str(query.filters.get("cliente_id") or "")
        rows = [r for r in self.profiles if str(r.get("cliente_id")) == cid]
        return _FakeResult(data=rows)


class _FakeMaps(MapsService):
    def __init__(self) -> None:
        pass

    async def get_distance_km(self, *_args: object, **_kwargs: object) -> float:
        return 120.0


class _MockPaymentService:
    async def create_mandate_setup_flow(self, cliente_id: str, success_url: str) -> dict[str, str]:
        assert cliente_id
        assert success_url
        return {"redirect_url": "https://gocardless.example/redirect/setup-flow"}


def _user(role: str, *, empresa_id: str, cliente_id: str | None = None) -> UserOut:
    return UserOut(
        username=f"{role}@qa.local",
        empresa_id=UUID(empresa_id),
        rol="user",
        rbac_role=role,
        cliente_id=UUID(cliente_id) if cliente_id else None,
        usuario_id=UUID("99999999-9999-9999-9999-999999999999"),
    )


@pytest.mark.asyncio
async def test_e2e_onboarding_and_credit_lock(client) -> None:
    empresa_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cliente_id = "11111111-1111-1111-1111-111111111111"
    db = _FakeDb(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        cliente_email="cliente.demo@example.com",
    )
    current_ctx = {"kind": "admin"}
    admin_headers = {
        "Authorization": f"Bearer {create_access_token(subject='admin@qa.local', empresa_id=empresa_id, rbac_role='traffic_manager')}"
    }

    def _current_user() -> UserOut:
        if current_ctx["kind"] == "cliente":
            return _user("cliente", empresa_id=empresa_id, cliente_id=cliente_id)
        return _user("traffic_manager", empresa_id=empresa_id)

    async def _db_dep() -> _FakeDb:
        return db

    async def _maps_dep() -> _FakeMaps:
        return _FakeMaps()

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_current_user] = _current_user
    app.dependency_overrides[deps.bind_write_context] = _current_user
    app.dependency_overrides[deps.require_portal_cliente] = _current_user
    app.dependency_overrides[deps.get_db] = _db_dep
    app.dependency_overrides[deps.get_db_admin] = _db_dep
    app.dependency_overrides[deps.get_maps_service] = _maps_dep
    app.dependency_overrides[deps.get_payment_service] = lambda: _MockPaymentService()

    try:
        # Paso 1: Admin invita al cliente.
        res_invite = await client.post(f"/api/v1/clientes/{cliente_id}/invitar")
        assert res_invite.status_code in (200, 201, 202)
        assert db.invites_sent == ["cliente.demo@example.com"]

        porte_payload = {
            "cliente_id": cliente_id,
            "fecha": date.today().isoformat(),
            "origen": "Madrid",
            "destino": "Valencia",
            "km_estimados": 320,
            "bultos": 10,
            "descripcion": "Carga paletizada",
            "precio_pactado": 980.0,
        }

        # Paso 2: Admin intenta crear porte -> bloqueado por onboarding incompleto.
        res_porte_blocked = await client.post(
            "/api/v1/portes/",
            json=porte_payload,
            headers=admin_headers,
        )
        assert res_porte_blocked.status_code == 403
        assert "Onboarding incompleto" in str(res_porte_blocked.json().get("detail", ""))

        # Paso 3: Contexto cliente consulta su riesgo.
        current_ctx["kind"] = "cliente"
        res_risk = await client.get("/api/v1/portal/onboarding/my-risk")
        assert res_risk.status_code == 200
        body_risk = res_risk.json()
        assert "score" in body_risk
        assert "creditLimitEur" in body_risk

        # Paso 4: Cliente acepta riesgo.
        res_accept = await client.post("/api/v1/portal/onboarding/accept-risk")
        assert res_accept.status_code == 200
        assert db.clientes[cliente_id]["riesgo_aceptado"] is True

        # Paso 5: Admin vuelve a crear porte -> ahora permitido.
        current_ctx["kind"] = "admin"
        res_porte_ok = await client.post(
            "/api/v1/portes/",
            json=porte_payload,
            headers=admin_headers,
        )
        assert res_porte_ok.status_code in (200, 201)

        # Paso 6: Cliente inicia setup de mandato (mock GoCardless).
        current_ctx["kind"] = "cliente"
        res_setup = await client.post("/api/v1/payments/gocardless/mandates/setup")
        assert res_setup.status_code == 200
        assert "redirect_url" in res_setup.json()
    finally:
        app.dependency_overrides.clear()

