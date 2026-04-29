from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# Aislamiento: variables mínimas para imports/config de app.
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "unit-test-jwt-secret-at-least-32-chars")
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-app-jwt-secret-32-characters!")
os.environ.setdefault("ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("DEV_MODE", "true")

from app.services.facturas_service import FacturasService


@dataclass
class _FakeQuery:
    table_name: str
    filters: dict[str, Any] = field(default_factory=dict)
    in_filters: dict[str, list[str]] = field(default_factory=dict)

    def select(self, _fields: str) -> _FakeQuery:
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def in_(self, key: str, values: list[str]) -> _FakeQuery:
        self.in_filters[key] = values
        return self

    def limit(self, _value: int) -> _FakeQuery:
        return self


def _build_mock_db(*, factura_row: dict[str, Any], porte_rows: list[dict[str, Any]]) -> MagicMock:
    db = MagicMock(name="supabase_db_mock")

    def _table(name: str) -> _FakeQuery:
        return _FakeQuery(table_name=name)

    async def _execute(query: _FakeQuery) -> Any:
        if query.table_name == "facturas":
            factura_id = int(query.filters.get("id", 0))
            empresa_id = str(query.filters.get("empresa_id", "")).strip()
            if (
                int(factura_row.get("id", 0)) == factura_id
                and str(factura_row.get("empresa_id", "")).strip() == empresa_id
            ):
                return SimpleNamespace(data=[dict(factura_row)])
            return SimpleNamespace(data=[])

        if query.table_name == "portes":
            empresa_id = str(query.filters.get("empresa_id", "")).strip()
            ids = set(query.in_filters.get("id", []))
            rows = [
                dict(row)
                for row in porte_rows
                if str(row.get("empresa_id", "")).strip() == empresa_id
                and str(row.get("id", "")) in ids
            ]
            return SimpleNamespace(data=rows)

        return SimpleNamespace(data=[])

    db.table.side_effect = _table
    db.execute.side_effect = _execute
    return db


@pytest.mark.asyncio
async def test_recalculate_invoice_triggers_on_esg_drift_for_unsealed_invoice() -> None:
    empresa_id = str(uuid4())
    porte_id = str(uuid4())
    factura_row = {
        "id": 101,
        "empresa_id": empresa_id,
        "hash_factura": "",
        "hash_registro": "",
        "is_finalized": False,
        "base_imponible": "1500.00",
        "cuota_iva": "315.00",
        "porte_lineas_snapshot": [
            {
                "porte_id": porte_id,
                "precio_pactado": "1500.00",
                "km_estimados": "100.000",
                "peso_ton": "10.000",
                "tipo_iva_porcentaje": "21.00",
                "aplicar_recargo_equivalencia": False,
                "retencion_irpf_porcentaje": "0.00",
            }
        ],
    }
    porte_rows = [
        {
            "id": porte_id,
            "empresa_id": empresa_id,
            "km_estimados": "120.000",
            "peso_ton": "12.000",
        }
    ]
    db = _build_mock_db(factura_row=factura_row, porte_rows=porte_rows)
    service = FacturasService(db=db)  # type: ignore[arg-type]

    out = await service.recalculate_invoice(empresa_id=empresa_id, factura_id=101)

    assert out.recalculate_triggered is True
    assert out.coste_operativo_recalculado == Decimal("892.80")
    assert out.margen_bruto_recalculado == Decimal("607.20")
    assert out.base_imponible == Decimal("1500.00")


@pytest.mark.asyncio
async def test_recalculate_invoice_does_not_trigger_when_invoice_is_finalized() -> None:
    empresa_id = str(uuid4())
    porte_id = str(uuid4())
    factura_row = {
        "id": 202,
        "empresa_id": empresa_id,
        "hash_factura": "",
        "hash_registro": "",
        "is_finalized": True,
        "base_imponible": "1500.00",
        "cuota_iva": "315.00",
        "porte_lineas_snapshot": [
            {
                "porte_id": porte_id,
                "precio_pactado": "1500.00",
                "km_estimados": "100.000",
                "peso_ton": "10.000",
                "tipo_iva_porcentaje": "21.00",
                "aplicar_recargo_equivalencia": False,
                "retencion_irpf_porcentaje": "0.00",
            }
        ],
    }
    porte_rows = [
        {
            "id": porte_id,
            "empresa_id": empresa_id,
            "km_estimados": "120.000",
            "peso_ton": "12.000",
        }
    ]
    db = _build_mock_db(factura_row=factura_row, porte_rows=porte_rows)
    service = FacturasService(db=db)  # type: ignore[arg-type]

    out = await service.recalculate_invoice(empresa_id=empresa_id, factura_id=202)

    assert out.recalculate_triggered is False
    assert out.coste_operativo_recalculado is None
    assert out.margen_bruto_recalculado is None
    assert out.base_imponible == Decimal("1500.00")


@pytest.mark.asyncio
async def test_recalculate_invoice_blocks_when_invoice_is_sealed_with_hash_chain() -> None:
    empresa_id = str(uuid4())
    porte_id = str(uuid4())
    factura_row = {
        "id": 303,
        "empresa_id": empresa_id,
        "hash_factura": "sealed-hash",
        "hash_registro": "sealed-registry-hash",
        "is_finalized": True,
        "base_imponible": "1500.00",
        "cuota_iva": "315.00",
        "porte_lineas_snapshot": [
            {
                "porte_id": porte_id,
                "precio_pactado": "1500.00",
                "km_estimados": "100.000",
                "peso_ton": "10.000",
                "tipo_iva_porcentaje": "21.00",
                "aplicar_recargo_equivalencia": False,
                "retencion_irpf_porcentaje": "0.00",
            }
        ],
    }
    porte_rows = [
        {
            "id": porte_id,
            "empresa_id": empresa_id,
            "km_estimados": "120.000",
            "peso_ton": "12.000",
        }
    ]
    db = _build_mock_db(factura_row=factura_row, porte_rows=porte_rows)
    service = FacturasService(db=db)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="inalterabilidad"):
        await service.recalculate_invoice(empresa_id=empresa_id, factura_id=303)

    # Integridad fiscal: al estar sellada, no debe leer los portes actuales.
    assert db.execute.call_count == 1
