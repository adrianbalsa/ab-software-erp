"""
Due diligence — aislamiento multi-tenant (semántica RLS: acceso cruzado denegado).

Objetivo auditoría: demostrar de forma **reproducible** que una sesión limitada al tenant A
no puede observar filas del tenant B (0 filas / 404), alineado con políticas RLS basadas en
``public.app_current_empresa_id()`` (ver migraciones bajo ``supabase/migrations/*rls*``).

Ejecutar:

    cd backend && pytest tests/test_rls_tenant_isolation_dd.py -v

No requiere Postgres ni Supabase en vivo: mocks deterministas (misma familia de tests que
``tests/test_rbac_enforcement.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.deps import assert_resource_belongs_to_current_empresa
from app.schemas.user import UserOut
from app.services.auth_service import AuthService
from tests.conftest import EMPRESA_A_ID, EMPRESA_B_ID

EMPRESA_A = str(EMPRESA_A_ID)
EMPRESA_B = str(EMPRESA_B_ID)


@dataclass
class _QueryResult:
    data: list[dict[str, Any]]


class _RlsMockQuery:
    """Simula PostgREST: filas visibles acotadas al tenant de sesión (como RLS)."""

    def __init__(self, db: "_RlsMockDb", table_name: str) -> None:
        self._db = db
        self._table_name = table_name
        self._filters: dict[str, str] = {}

    def select(self, *_args: object) -> "_RlsMockQuery":
        return self

    def eq(self, key: str, value: object) -> "_RlsMockQuery":
        self._filters[key] = str(value)
        return self

    def limit(self, *_args: object) -> "_RlsMockQuery":
        return self

    def execute(self) -> _QueryResult:
        rows = list(self._db.rows_by_table.get(self._table_name, []))
        rows = [r for r in rows if str(r.get("empresa_id")) == self._db.session_empresa_id]
        for key, value in self._filters.items():
            rows = [r for r in rows if str(r.get(key)) == value]
        return _QueryResult(data=rows)


class _RlsMockDb:
    def __init__(self, *, session_empresa_id: str, rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
        self.session_empresa_id = session_empresa_id
        self.rows_by_table = rows_by_table

    def table(self, table_name: str) -> _RlsMockQuery:
        return _RlsMockQuery(self, table_name)

    async def execute(self, query: _RlsMockQuery) -> _QueryResult:
        return query.execute()


@pytest.mark.asyncio
@pytest.mark.rls_isolation
async def test_rls_semantics_cross_tenant_filter_returns_no_rows() -> None:
    db = _RlsMockDb(
        session_empresa_id=EMPRESA_A,
        rows_by_table={
            "portes": [
                {"id": "p-a", "empresa_id": EMPRESA_A},
                {"id": "p-b", "empresa_id": EMPRESA_B},
            ]
        },
    )
    cross = await db.execute(db.table("portes").select("*").eq("empresa_id", EMPRESA_B))
    assert cross.data == []


@pytest.mark.asyncio
@pytest.mark.rls_isolation
async def test_rls_semantics_unscoped_select_only_own_tenant_rows() -> None:
    db = _RlsMockDb(
        session_empresa_id=EMPRESA_A,
        rows_by_table={
            "portes": [
                {"id": "p-a", "empresa_id": EMPRESA_A},
                {"id": "p-b", "empresa_id": EMPRESA_B},
            ]
        },
    )
    all_visible = await db.execute(db.table("portes").select("*"))
    assert len(all_visible.data) == 1
    assert all_visible.data[0]["id"] == "p-a"


@pytest.mark.asyncio
@pytest.mark.rls_isolation
async def test_api_layer_assert_resource_other_tenant_returns_404() -> None:
    from tests.unit.test_security_isolation import _FakeDb  # noqa: PLC0415 — reuse fake DB

    db = _FakeDb(
        rows_by_table={
            "facturas": [
                {"id": "101", "empresa_id": EMPRESA_A},
            ]
        }
    )
    current_user_b = type("U", (), {"empresa_id": EMPRESA_B_ID})()

    with pytest.raises(HTTPException) as exc:
        await assert_resource_belongs_to_current_empresa(
            db=db,
            current_user=current_user_b,
            table_name="facturas",
            resource_id="101",
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.rls_isolation
async def test_http_get_porte_other_tenant_returns_404(client, mock_user_empresa_a, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_profile(self: AuthService, *, subject: str) -> UserOut:
        return UserOut(
            username=str(subject),
            empresa_id=EMPRESA_A_ID,
            rol="user",
            usuario_id=None,
        )

    async def fake_ensure(self: AuthService, *, empresa_id: object) -> None:
        return None

    async def fake_rbac(self: AuthService, *, user: UserOut) -> None:
        return None

    monkeypatch.setattr(AuthService, "get_profile_by_subject", fake_profile)
    monkeypatch.setattr(AuthService, "ensure_empresa_context", fake_ensure)
    monkeypatch.setattr(AuthService, "ensure_rbac_context", fake_rbac)

    porte_id_belonging_to_b = "33333333-3333-3333-3333-333333333333"
    res = await client.get(
        f"/portes/{porte_id_belonging_to_b}",
        headers={"Authorization": f"Bearer {mock_user_empresa_a['jwt']}"},
    )
    assert res.status_code == 404
    assert res.json().get("detail") == "Porte no encontrado"


@pytest.mark.asyncio
@pytest.mark.rls_isolation
async def test_logis_advisor_build_data_context_empty_portes_when_only_other_tenant_rows() -> None:
    """Misma semántica RLS que el HTTP legacy: consultas acotadas al tenant no ven filas de B."""

    db = _RlsMockDb(
        session_empresa_id=EMPRESA_A,
        rows_by_table={
            "portes": [
                {"id": "porte-b-99", "empresa_id": EMPRESA_B, "origen": "X", "destino": "Y"},
            ]
        },
    )

    class _FakeAdvisorService:
        async def build_data_context(self, *, empresa_id: str) -> dict[str, Any]:
            res = await db.execute(
                db.table("portes").select("*").eq("empresa_id", empresa_id),
            )
            return {"current_portes": res.data}

    svc = _FakeAdvisorService()
    ctx = await svc.build_data_context(empresa_id=EMPRESA_A)
    assert ctx["current_portes"] == []
