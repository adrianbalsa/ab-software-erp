from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

import pytest

from app.schemas.porte import PorteCreate
from app.services.portes_service import PorteDomainError, PortesService


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

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self

    def is_(self, *_args: object) -> _FakeQuery:
        return self


class _FakeDb:
    def __init__(self, *, client_row: dict[str, Any] | None) -> None:
        self.client_row = client_row
        self.inserted_porte: dict[str, Any] | None = None

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.table == "clientes" and query.action == "select":
            return _FakeResult(data=[self.client_row] if self.client_row is not None else [])
        if query.table == "portes" and query.action == "insert":
            row = {"id": "22222222-2222-2222-2222-222222222222", **query.payload}
            self.inserted_porte = row
            return _FakeResult(data=[row])
        return _FakeResult(data=[])


class _FakeMaps:
    async def get_distance_km(self, *_args: object, **_kwargs: object) -> float:
        return 120.0


@pytest.mark.asyncio
async def test_create_porte_denied_when_cliente_risk_not_accepted() -> None:
    db = _FakeDb(client_row={"id": "c1", "riesgo_aceptado": False})
    svc = PortesService(db=db, maps=_FakeMaps())
    payload = PorteCreate(
        cliente_id=UUID("11111111-1111-1111-1111-111111111111"),
        fecha=date(2026, 1, 10),
        origen="Madrid",
        destino="Valencia",
        km_estimados=350,
        bultos=8,
        descripcion="Carga general",
        precio_pactado=980.0,
    )

    with pytest.raises(
        PorteDomainError,
        match="Operación denegada: El cliente no ha aceptado las condiciones de riesgo comercial \\(Onboarding incompleto\\)\\.",
    ):
        await svc.create_porte(
            empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            porte_in=payload,
        )
    assert db.inserted_porte is None


@pytest.mark.asyncio
async def test_create_porte_allows_when_cliente_risk_accepted() -> None:
    db = _FakeDb(client_row={"id": "c1", "riesgo_aceptado": True})
    svc = PortesService(db=db, maps=_FakeMaps())
    payload = PorteCreate(
        cliente_id=UUID("11111111-1111-1111-1111-111111111111"),
        fecha=date(2026, 1, 10),
        origen="Madrid",
        destino="Valencia",
        km_estimados=350,
        bultos=8,
        descripcion="Carga general",
        precio_pactado=980.0,
    )

    out = await svc.create_porte(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        porte_in=payload,
    )

    assert out.cliente_id == payload.cliente_id
    assert out.origen == "Madrid"
    assert db.inserted_porte is not None

