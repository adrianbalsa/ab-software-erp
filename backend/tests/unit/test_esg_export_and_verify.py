"""Export ESG sin PII (ISO 14083) y firma webhook de verificación externa."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import date

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE
from app.services.esg_audit_service import (
    esg_external_webhook_signature_hex,
    verify_esg_external_webhook_signature,
)
from app.services.esg_export_service import EsgExportService, _litros_implied_diesel_iso14083


def test_litros_implied_from_co2_iso14083() -> None:
    kg = 267.0
    assert _litros_implied_diesel_iso14083(kg_co2=kg) == 100.0
    assert _litros_implied_diesel_iso14083(kg_co2=0.0) == 0.0


def test_webhook_hmac_roundtrip() -> None:
    secret = "test-secret"
    body = b'{"verification_code":"abc-123-uuid"}'
    sig = esg_external_webhook_signature_hex(secret=secret, raw_body=body)
    assert len(sig) == 64
    assert verify_esg_external_webhook_signature(secret=secret, raw_body=body, signature_header=sig)
    assert verify_esg_external_webhook_signature(
        secret=secret, raw_body=body, signature_header=f"sha256={sig}"
    )
    assert not verify_esg_external_webhook_signature(secret=secret, raw_body=body, signature_header="deadbeef")
    assert not verify_esg_external_webhook_signature(
        secret="other", raw_body=body, signature_header=sig
    )


def test_webhook_hmac_matches_raw_hmac() -> None:
    secret = "x"
    body = b"{}"
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert esg_external_webhook_signature_hex(secret=secret, raw_body=body) == expected


class _FakeResult:
    def __init__(self, data: list | None) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, parent: "_FakeDB", table: str) -> None:
        self._parent = parent
        self._table = table
        self._action = "select"
        self._cols = "*"
        self._filters: list[tuple[str, str, object]] = []

    def select(self, cols: str) -> "_FakeQuery":
        self._cols = cols
        return self

    def eq(self, col: str, val: object) -> "_FakeQuery":
        self._filters.append(("eq", col, val))
        return self

    def gte(self, col: str, val: object) -> "_FakeQuery":
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col: str, val: object) -> "_FakeQuery":
        self._filters.append(("lte", col, val))
        return self

    def in_(self, col: str, vals: list) -> "_FakeQuery":
        self._filters.append(("in", col, vals))
        return self

    def is_(self, col: str, val: object) -> "_FakeQuery":
        self._filters.append(("is", col, val))
        return self

    def limit(self, _n: int) -> "_FakeQuery":
        return self


class _FakeDB:
    def __init__(self, porte_rows: list[dict], flota_rows: list[dict]) -> None:
        self._porte_rows = porte_rows
        self._flota_rows = flota_rows

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)

    async def execute(self, q: _FakeQuery) -> _FakeResult:
        if q._table == "portes":
            return _FakeResult(list(self._porte_rows))
        if q._table == "flota":
            return _FakeResult(list(self._flota_rows))
        if q._table == "vehiculos":
            return _FakeResult([])
        return _FakeResult([])


def test_export_rows_only_allowed_columns() -> None:
    empresa = "00000000-0000-4000-8000-0000000000aa"
    porte_rows = [
        {
            "id": "porte-1",
            "vehiculo_id": "00000000-0000-4000-8000-0000000000bb",
            "km_estimados": 100.0,
            "km_reales": 99.5,
            "co2_emitido": 61.69,
            "fecha": "2026-04-01",
            "estado": "facturado",
        }
    ]
    flota_rows = [
        {
            "id": "00000000-0000-4000-8000-0000000000bb",
            "certificacion_emisiones": "Euro VI",
            "normativa_euro": "Euro VI",
        }
    ]
    db = _FakeDB(porte_rows, flota_rows)
    svc = EsgExportService(db)  # type: ignore[arg-type]

    async def _run():
        return await svc.build_masked_emissions_rows(
            empresa_id=empresa,
            fecha_inicio=date(2026, 4, 1),
            fecha_fin=date(2026, 4, 30),
        )

    rows, meta = asyncio.run(_run())
    assert meta["row_count"] == 1
    assert "empresa_id" in meta

    async def _run_redacted():
        return await svc.build_masked_emissions_rows(
            empresa_id=empresa,
            fecha_inicio=date(2026, 4, 1),
            fecha_fin=date(2026, 4, 30),
            redact_workspace=True,
        )

    _rows2, meta2 = asyncio.run(_run_redacted())
    assert meta2.get("empresa_id") is None
    assert meta2.get("tenant_scope") == "redacted_for_external_auditor"

    r = rows[0]
    assert set(r.keys()) == {"Fecha", "Euro_Class", "Km", "Litros", "Kg_CO2"}
    assert "porte-1" not in json.dumps(rows)
    assert r["Fecha"] == "2026-04-01"
    assert r["Euro_Class"] == "Euro VI"
    assert r["Km"] == 99.5
    assert r["Kg_CO2"] == 61.69
    assert r["Litros"] == round(61.69 / ISO_14083_DIESEL_CO2_KG_PER_LITRE, 6)
