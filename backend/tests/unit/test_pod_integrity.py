from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.schemas.user import UserOut

# Evita dependencias opcionales de generación PDF durante import del servicio.
import sys
sys.modules.setdefault("PIL", MagicMock(name="PIL_test_double"))
sys.modules.setdefault("PIL.Image", MagicMock(name="PIL_Image_test_double"))

from app.services.portes_service import PortesService


@dataclass
class _FakeResult:
    data: list[dict[str, Any]] | None = None


class _FakeQuery:
    def __init__(self, table: str, action: str) -> None:
        self.table = table
        self.action = action
        self.filters: dict[str, Any] = {}
        self.payload: dict[str, Any] | None = None

    def select(self, *_args: object) -> _FakeQuery:
        return self

    def update(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self

    # Compat con filter_not_deleted(...)
    def not_(self) -> _FakeQuery:
        return self

    def is_(self, *_args: object) -> _FakeQuery:
        return self


class _FakeDb:
    def __init__(self, km_estimados: Any, rpc_raises: bool = False) -> None:
        self._row = {
            "id": "11111111-1111-1111-1111-111111111111",
            "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "vehiculo_id": "22222222-2222-2222-2222-222222222222",
            "estado": "pendiente",
            "km_estimados": km_estimados,
            "conductor_asignado_id": "33333333-3333-3333-3333-333333333333",
        }
        self.rpc_raises = rpc_raises
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name, "select")

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.table == "portes" and query.action == "select":
            return _FakeResult(data=[self._row])
        if query.table == "portes" and query.action == "update":
            if query.payload:
                self._row.update(query.payload)
            return _FakeResult(data=[self._row])
        return _FakeResult(data=[])

    async def rpc(self, fn_name: str, params: dict[str, Any]) -> None:
        self.rpc_calls.append((fn_name, params))
        if self.rpc_raises:
            raise RuntimeError("rpc failed")


def _driver_user() -> UserOut:
    return UserOut(
        username="driver@test.local",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        rol="user",
        usuario_id=UUID("33333333-3333-3333-3333-333333333333"),
        assigned_vehiculo_id=UUID("22222222-2222-2222-2222-222222222222"),
        rbac_role="driver",
        cliente_id=None,
    )


@pytest.mark.asyncio
async def test_firmar_entrega_reports_odometer_success_and_decimal_km() -> None:
    db = _FakeDb(km_estimados="123.456", rpc_raises=False)
    service = PortesService(db=db, maps=None)  # type: ignore[arg-type]

    out = await service.firmar_entrega(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        porte_id="11111111-1111-1111-1111-111111111111",
        current_user=_driver_user(),
        firma_b64="A" * 40,
        nombre_consignatario="Consignatario QA",
    )

    assert out["estado"] == "Entregado"
    assert out["odometro_actualizado"] is True
    assert out["odometro_error"] is None
    assert db.rpc_calls
    fn_name, params = db.rpc_calls[0]
    assert fn_name == "increment_vehiculo_odometro"
    assert params["p_km"] == "123.46"


@pytest.mark.asyncio
async def test_firmar_entrega_reports_odometer_failure_without_breaking_pod() -> None:
    db = _FakeDb(km_estimados=50, rpc_raises=True)
    service = PortesService(db=db, maps=None)  # type: ignore[arg-type]

    out = await service.firmar_entrega(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        porte_id="11111111-1111-1111-1111-111111111111",
        current_user=_driver_user(),
        firma_b64="B" * 40,
        nombre_consignatario="Consignatario QA",
    )

    assert out["estado"] == "Entregado"
    assert out["odometro_actualizado"] is False
    assert isinstance(out["odometro_error"], str)
