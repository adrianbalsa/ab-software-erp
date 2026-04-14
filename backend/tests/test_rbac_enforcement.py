from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any
from uuid import UUID

import pytest

from unittest.mock import MagicMock

sys.modules.setdefault("rapidfuzz", MagicMock(name="rapidfuzz_test_double"))
sys.modules.setdefault("litellm", MagicMock(name="litellm_test_double"))
sys.modules.setdefault("anthropic", MagicMock(name="anthropic_test_double"))

from app.api import deps
from app.models.auth import UserRole
from app.schemas.user import UserOut


EMPRESA_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
EMPRESA_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@dataclass
class _QueryResult:
    data: list[dict[str, Any]]


class _RlsMockQuery:
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
        # Simula RLS por tenant: aunque el atacante no filtre, solo ve su empresa.
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


class _RlsDenyDb:
    def table(self, _table_name: str) -> "_RlsDenyDb":
        return self

    def select(self, *_args: object) -> "_RlsDenyDb":
        return self

    def eq(self, *_args: object) -> "_RlsDenyDb":
        return self

    async def execute(self, _query: object) -> _QueryResult:
        raise PermissionError("new row violates row-level security policy for table portes")


def _transportista_user() -> UserOut:
    return UserOut(
        username="transportista@qa.local",
        empresa_id=UUID(EMPRESA_A),
        role=UserRole.TRANSPORTISTA,
        rol="transportista",
        rbac_role="driver",
        usuario_id=UUID("11111111-1111-1111-1111-111111111111"),
    )


@pytest.mark.asyncio
async def test_transportista_gets_403_on_ai_and_reports_endpoints(client) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_current_user] = _transportista_user

    try:
        # En esta API /ai/consult es POST; así validamos el RoleChecker real.
        consult_res = await client.post("/ai/consult", json={"query": "Diagnóstico de prueba"})
        assert consult_res.status_code == 403
        assert "Acceso denegado" in consult_res.json().get("detail", "")

        report_res = await client.get(f"/reports/efficiency/{EMPRESA_A}")
        assert report_res.status_code == 403
        assert "Acceso denegado" in report_res.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mock_session_rls_blocks_manual_portes_queries_cross_tenant() -> None:
    db = _RlsMockDb(
        session_empresa_id=EMPRESA_A,
        rows_by_table={
            "portes": [
                {"id": "porte-a-1", "empresa_id": EMPRESA_A, "ref": "A"},
                {"id": "porte-b-1", "empresa_id": EMPRESA_B, "ref": "B"},
            ]
        },
    )

    # Ataque manual: intentar leer explícitamente filas de empresa B.
    cross_tenant = await db.execute(
        db.table("portes").select("*").eq("empresa_id", EMPRESA_B),
    )
    assert cross_tenant.data == []

    # Incluso sin filtro explícito, RLS solo devuelve filas del tenant de la sesión.
    visible_rows = await db.execute(db.table("portes").select("*"))
    assert len(visible_rows.data) == 1
    assert all(str(row.get("empresa_id")) == EMPRESA_A for row in visible_rows.data)


@pytest.mark.asyncio
async def test_gold_bypass_rolechecker_but_rls_still_blocks_data(client, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _RlsMockDb(
        session_empresa_id=EMPRESA_A,
        rows_by_table={
            "portes": [
                {"id": "porte-b-99", "empresa_id": EMPRESA_B, "origen": "Sevilla", "destino": "Bilbao"},
            ]
        },
    )

    class _FakeAdvisorService:
        def openai_configured(self) -> bool:
            return True

        async def build_data_context(self, *, empresa_id: str) -> dict[str, Any]:
            res = await db.execute(
                db.table("portes").select("*").eq("empresa_id", empresa_id),
            )
            return {"current_portes": res.data}

        async def generate_diagnostic(self, *, data_context: dict[str, Any], user_query: str) -> dict[str, Any]:
            _ = user_query
            return {
                "summary_headline": "RLS enforced",
                "profitability": {"status": "ok", "findings": [], "actions": []},
                "fiscal_safety": {"status": "ok", "findings": [], "actions": []},
                "liquidity": {"status": "ok", "findings": [], "actions": []},
                "risk_flags": [],
                "recommended_actions": [],
                "model": "test-double",
                "data_context": data_context,
            }

    async def _allow_all_rolechecker(self, current_user: UserOut) -> UserOut:
        _ = self
        return current_user

    monkeypatch.setattr(deps.RoleChecker, "__call__", _allow_all_rolechecker)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_current_user] = _transportista_user
    app.dependency_overrides[deps.get_logis_advisor_service] = lambda: _FakeAdvisorService()

    try:
        res = await client.post("/ai/consult", json={"query": "Intento de extracción masiva"})
        assert res.status_code == 200
        body = res.json()

        # Gold test: aunque el checker de API se haya saltado, RLS mantiene cero filas visibles.
        assert body["data_context"]["current_portes"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gold_bypass_rolechecker_rls_permission_error_is_still_enforced(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _RlsDenyDb()

    class _FakeAdvisorService:
        def openai_configured(self) -> bool:
            return True

        async def build_data_context(self, *, empresa_id: str) -> dict[str, Any]:
            _ = empresa_id
            await db.execute(db.table("portes").select("*").eq("empresa_id", EMPRESA_A))
            return {"current_portes": []}

        async def generate_diagnostic(self, *, data_context: dict[str, Any], user_query: str) -> dict[str, Any]:
            _ = (data_context, user_query)
            return {
                "summary_headline": "Should not reach diagnostic generation",
                "profitability": {"status": "ok", "findings": [], "actions": []},
                "fiscal_safety": {"status": "ok", "findings": [], "actions": []},
                "liquidity": {"status": "ok", "findings": [], "actions": []},
                "risk_flags": [],
                "recommended_actions": [],
            }

    async def _allow_all_rolechecker(self, current_user: UserOut) -> UserOut:
        _ = self
        return current_user

    monkeypatch.setattr(deps.RoleChecker, "__call__", _allow_all_rolechecker)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_current_user] = _transportista_user
    app.dependency_overrides[deps.get_logis_advisor_service] = lambda: _FakeAdvisorService()

    try:
        res = await client.post("/ai/consult", json={"query": "Intento de extracción con error RLS"})
        # El bypass de RoleChecker no evita que el fallo de capa de datos rompa la operación.
        assert res.status_code == 502
        assert "No se pudo generar el diagnóstico IA." in res.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()
