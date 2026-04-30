from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.verifactu_chain_repair import (
    diagnose_fingerprint_hash_chain,
    repair_recommendations,
)
from app.services.verifactu_service import VerifactuService


class _QueryStub:
    def select(self, _fields: str) -> "_QueryStub":
        return self

    def eq(self, _key: str, _value: Any) -> "_QueryStub":
        return self

    def order(self, _field: str, desc: bool = False) -> "_QueryStub":
        _ = desc
        return self

    def limit(self, _value: int) -> "_QueryStub":
        return self


@pytest.mark.asyncio
async def test_verificar_cadena_facturas_ok_sin_discrepancias(monkeypatch: pytest.MonkeyPatch) -> None:
    empresa_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    genesis = "11" * 32

    row1_hash = VerifactuService.generate_invoice_hash(
        {
            "num_factura": "FAC-2026-000001",
            "fecha_emision": "2026-04-29",
            "nif_emisor": "B12345678",
            "total_factura": "121.00",
        },
        genesis,
    )
    row2_hash = VerifactuService.generate_invoice_hash(
        {
            "num_factura": "FAC-2026-000002",
            "fecha_emision": "2026-04-30",
            "nif_emisor": "B12345678",
            "total_factura": "242.00",
        },
        row1_hash,
    )

    rows_desc = [
        {
            "id": 2,
            "numero_secuencial": 2,
            "num_factura": "FAC-2026-000002",
            "fecha_emision": "2026-04-30",
            "nif_emisor": "B12345678",
            "total_factura": "242.00",
            "hash_anterior": row1_hash,
            "hash_factura": row2_hash,
        },
        {
            "id": 1,
            "numero_secuencial": 1,
            "num_factura": "FAC-2026-000001",
            "fecha_emision": "2026-04-29",
            "nif_emisor": "B12345678",
            "total_factura": "121.00",
            "hash_anterior": genesis,
            "hash_factura": row1_hash,
        },
    ]

    db = MagicMock()
    db.table.return_value = _QueryStub()
    db.execute = AsyncMock(return_value=SimpleNamespace(data=rows_desc))

    monkeypatch.setattr("app.services.verifactu_service.pii_crypto.decrypt_pii", lambda v: v)
    monkeypatch.setattr(
        "app.services.verifactu_service.get_verifactu_genesis_hash_for_issuer",
        lambda issuer_id, issuer_nif=None: genesis,
    )

    report = await VerifactuService(db).verificar_cadena_facturas(empresa_id=empresa_id, limit=50)
    assert report["ok"] is True
    assert report["revisadas"] == 2
    assert report["discrepancies"] == []


@pytest.mark.asyncio
async def test_verificar_cadena_facturas_detecta_fail_de_hash_anterior_y_hash_factura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empresa_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    genesis = "22" * 32

    row1_hash = VerifactuService.generate_invoice_hash(
        {
            "num_factura": "FAC-2026-000001",
            "fecha_emision": "2026-04-29",
            "nif_emisor": "B12345678",
            "total_factura": "121.00",
        },
        genesis,
    )

    rows_desc = [
        {
            "id": 2,
            "numero_secuencial": 2,
            "num_factura": "FAC-2026-000002",
            "fecha_emision": "2026-04-30",
            "nif_emisor": "B12345678",
            "total_factura": "242.00",
            "hash_anterior": "BADPREV",
            "hash_factura": "BADHASH",
        },
        {
            "id": 1,
            "numero_secuencial": 1,
            "num_factura": "FAC-2026-000001",
            "fecha_emision": "2026-04-29",
            "nif_emisor": "B12345678",
            "total_factura": "121.00",
            "hash_anterior": genesis,
            "hash_factura": row1_hash,
        },
    ]

    db = MagicMock()
    db.table.return_value = _QueryStub()
    db.execute = AsyncMock(return_value=SimpleNamespace(data=rows_desc))

    monkeypatch.setattr("app.services.verifactu_service.pii_crypto.decrypt_pii", lambda v: v)
    monkeypatch.setattr(
        "app.services.verifactu_service.get_verifactu_genesis_hash_for_issuer",
        lambda issuer_id, issuer_nif=None: genesis,
    )

    report = await VerifactuService(db).verificar_cadena_facturas(empresa_id=empresa_id, limit=50)
    assert report["ok"] is False
    tipos = {d["tipo"] for d in report["discrepancies"]}
    assert "hash_anterior" in tipos
    assert "hash_factura" in tipos


def test_repair_recommendations_resume_ok_fail_and_repair() -> None:
    genesis = "33" * 32
    rows = [
        {
            "id": 1,
            "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "nif_emisor": "B12345678",
            "nif_receptor": "A12345678",
            "numero_factura": "FAC-2026-000001",
            "fecha_emision": "2026-04-29",
            "total_factura": "121.00",
            "previous_fingerprint": "BADPREV",
            "fingerprint_hash": "BADHASH",
        }
    ]

    fingerprint_report = diagnose_fingerprint_hash_chain(rows, genesis_hash=genesis)
    assert fingerprint_report["ok"] is False

    recs = repair_recommendations(
        db_discrepancies=[{"tipo": "hash_factura", "factura_id": 1}],
        fingerprint_hash_report=fingerprint_report,
        lang="en",
    )
    assert len(recs) >= 2
    assert any("discrepancy" in r.lower() for r in recs)
    assert any("previous_fingerprint chain" in r.lower() for r in recs)
