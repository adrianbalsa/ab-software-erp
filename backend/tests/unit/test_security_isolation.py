from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.api.deps import assert_resource_belongs_to_current_empresa
from app.schemas.cliente import ClienteCreate
from app.services.clientes_service import ClientesService


@dataclass
class _FakeResult:
    data: list[dict[str, Any]] | None = None


class _FakeQuery:
    def __init__(self, table: str) -> None:
        self.table = table
        self.action = "select"
        self.filters: dict[str, Any] = {}
        self.payload: dict[str, Any] | None = None

    def select(self, *_args: object) -> _FakeQuery:
        self.action = "select"
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "insert"
        self.payload = payload
        return self


class _FakeDb:
    def __init__(self, rows_by_table: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.rows_by_table = rows_by_table or {}
        self.last_insert_payload: dict[str, Any] | None = None

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.action == "insert":
            payload = dict(query.payload or {})
            payload.setdefault("id", str(uuid4()))
            self.last_insert_payload = payload
            return _FakeResult(data=[payload])

        rows = list(self.rows_by_table.get(query.table, []))
        for key, value in query.filters.items():
            rows = [r for r in rows if str(r.get(key)) == str(value)]
        return _FakeResult(data=rows)


@pytest.mark.asyncio
async def test_tenant_isolation_blocks_cross_company_resource_access() -> None:
    empresa_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    empresa_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    db = _FakeDb(
        rows_by_table={
            "facturas": [
                {"id": "101", "empresa_id": empresa_a},
            ]
        }
    )
    current_user_b = SimpleNamespace(empresa_id=UUID(empresa_b))

    with pytest.raises(HTTPException) as exc:
        await assert_resource_belongs_to_current_empresa(
            db=db,
            current_user=current_user_b,
            table_name="facturas",
            resource_id="101",
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation_allows_same_company_resource_access() -> None:
    empresa_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    db = _FakeDb(
        rows_by_table={
            "facturas": [
                {"id": "101", "empresa_id": empresa_a},
            ]
        }
    )
    current_user_a = SimpleNamespace(empresa_id=UUID(empresa_a))

    await assert_resource_belongs_to_current_empresa(
        db=db,
        current_user=current_user_a,
        table_name="facturas",
        resource_id="101",
    )


@pytest.mark.asyncio
async def test_clientes_service_injects_empresa_id_on_create() -> None:
    db = _FakeDb()
    service = ClientesService(db=db)
    empresa_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    payload = ClienteCreate(
        nombre="Cliente Demo",
        nif=None,
        email="cliente@example.com",
        telefono="+34 600 000 000",
        direccion="Madrid",
    )

    await service.create_cliente(empresa_id=empresa_id, payload=payload)

    assert db.last_insert_payload is not None
    assert db.last_insert_payload.get("empresa_id") == empresa_id
