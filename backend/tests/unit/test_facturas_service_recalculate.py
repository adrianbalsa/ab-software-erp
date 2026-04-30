from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.services.facturas_service import FacturasService


@dataclass
class _FakeQuery:
    table_name: str
    selected: str = "*"
    filters: dict[str, Any] = field(default_factory=dict)
    in_filters: dict[str, list[str]] = field(default_factory=dict)

    def select(self, fields: str) -> _FakeQuery:
        self.selected = fields
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def in_(self, key: str, values: list[str]) -> _FakeQuery:
        self.in_filters[key] = values
        return self

    def limit(self, _n: int) -> _FakeQuery:
        return self


class _FakeDb:
    def __init__(self, *, factura_row: dict[str, Any], porte_rows: list[dict[str, Any]]) -> None:
        self._factura_row = factura_row
        self._porte_rows = porte_rows

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(table_name=name)

    async def execute(self, query: _FakeQuery) -> Any:
        if query.table_name == "facturas":
            fid = int(query.filters.get("id", 0))
            eid = str(query.filters.get("empresa_id", "")).strip()
            row = dict(self._factura_row)
            if int(row.get("id", 0)) == fid and str(row.get("empresa_id", "")).strip() == eid:
                return SimpleNamespace(data=[row])
            return SimpleNamespace(data=[])

        if query.table_name == "portes":
            eid = str(query.filters.get("empresa_id", "")).strip()
            ids = set(query.in_filters.get("id", []))
            rows = [
                dict(r)
                for r in self._porte_rows
                if str(r.get("empresa_id", "")).strip() == eid and str(r.get("id", "")) in ids
            ]
            return SimpleNamespace(data=rows)

        return SimpleNamespace(data=[])


@pytest.mark.asyncio
async def test_recalculate_invoice_triggers_operational_recalc_when_route_or_weight_changes() -> None:
    eid = str(uuid4())
    pid = str(uuid4())
    factura_row = {
        "id": 77,
        "empresa_id": eid,
        "hash_factura": "",
        "hash_registro": "",
        "is_finalized": False,
        "base_imponible": "150.00",
        "cuota_iva": "31.50",
        "porte_lineas_snapshot": [
            {
                "porte_id": pid,
                "precio_pactado": "150.00",
                "km_estimados": "100.000",
                "peso_ton": "1.000",
                "tipo_iva_porcentaje": "21.00",
                "aplicar_recargo_equivalencia": False,
                "retencion_irpf_porcentaje": "0.00",
            }
        ],
    }
    porte_rows = [
        {
            "id": pid,
            "empresa_id": eid,
            "km_estimados": "120.500",
            "peso_ton": "1.250",
        }
    ]
    db = _FakeDb(factura_row=factura_row, porte_rows=porte_rows)
    service = FacturasService(db=db)  # type: ignore[arg-type]

    out = await service.recalculate_invoice(empresa_id=eid, factura_id=77)

    assert out.recalculate_triggered is True
    assert out.coste_operativo_recalculado == Decimal("93.39")
    assert out.margen_bruto_recalculado == Decimal("56.61")


@pytest.mark.asyncio
async def test_recalculate_invoice_does_not_trigger_operational_recalc_without_esg_change() -> None:
    eid = str(uuid4())
    pid = str(uuid4())
    factura_row = {
        "id": 88,
        "empresa_id": eid,
        "hash_factura": "",
        "hash_registro": "",
        "is_finalized": False,
        "base_imponible": "100.00",
        "cuota_iva": "21.00",
        "porte_lineas_snapshot": [
            {
                "porte_id": pid,
                "precio_pactado": "100.00",
                "km_estimados": "50.000",
                "peso_ton": "2.000",
                "tipo_iva_porcentaje": "21.00",
                "aplicar_recargo_equivalencia": False,
                "retencion_irpf_porcentaje": "0.00",
            }
        ],
    }
    porte_rows = [
        {
            "id": pid,
            "empresa_id": eid,
            "km_estimados": "50.000",
            "peso_ton": "2.000",
        }
    ]
    db = _FakeDb(factura_row=factura_row, porte_rows=porte_rows)
    service = FacturasService(db=db)  # type: ignore[arg-type]

    out = await service.recalculate_invoice(empresa_id=eid, factura_id=88)

    assert out.recalculate_triggered is False
    assert out.coste_operativo_recalculado is None
    assert out.margen_bruto_recalculado is None
