"""Cadena de hash: compatibilidad F1 vs ampliación R1 [cite: 2026-03-22]."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.aeat_qr_service import build_srei_verifactu_url, build_tike_verifactu_url
from app.services.verifactu_service import (
    VERIFACTU_CHAIN_SEED_HEX,
    VERIFACTU_INVOICE_GENESIS_HASH,
    VerifactuService,
)


def test_generar_hash_sin_campos_rect_igual_que_legacy() -> None:
    """Sin tipo ni RECT la cadena coincide con el algoritmo histórico."""
    h = VerifactuService.generar_hash_factura(
        nif_empresa="b12345678",
        nif_cliente="a87654321",
        num_factura="FAC-2025-000001",
        fecha="2025-03-22",
        total=121.0,
        hash_anterior="ab" * 32,
    )
    assert len(h) == 64
    h2 = VerifactuService.generar_hash_factura(
        nif_empresa="b12345678",
        nif_cliente="a87654321",
        num_factura="FAC-2025-000001",
        fecha="2025-03-22",
        total=121.0,
        hash_anterior="ab" * 32,
        tipo_factura=None,
        num_factura_rectificada=None,
    )
    assert h == h2


def test_generate_invoice_hash_usa_genesis_si_prev_vacio() -> None:
    inv = {
        "num_factura": "FAC-2026-000001",
        "fecha_emision": "2026-03-24",
        "nif_emisor": "B12345678",
        "total_factura": 121.0,
    }
    h_none = VerifactuService.generate_invoice_hash(inv, None)
    h_empty = VerifactuService.generate_invoice_hash(inv, "")
    h_genesis = VerifactuService.generate_invoice_hash(inv, VERIFACTU_INVOICE_GENESIS_HASH)
    assert h_none == h_empty == h_genesis
    assert len(h_none) == 64


def test_generar_hash_r1_incluye_tipo_y_rect_distinto() -> None:
    h_f1 = VerifactuService.generar_hash_factura(
        nif_empresa="B1",
        nif_cliente="C1",
        num_factura="R-2025-000002",
        fecha="2025-03-22",
        total=-121.0,
        hash_anterior="cd" * 32,
    )
    h_r1 = VerifactuService.generar_hash_factura(
        nif_empresa="B1",
        nif_cliente="C1",
        num_factura="R-2025-000002",
        fecha="2025-03-22",
        total=-121.0,
        hash_anterior="cd" * 32,
        tipo_factura="R1",
        num_factura_rectificada="FAC-2025-000001",
    )
    assert h_f1 != h_r1


def test_fingerprint_desde_eslabon_primera_factura_prev_none() -> None:
    fp, prev = VerifactuService.fingerprint_desde_eslabon_finalizado(
        prev_fingerprint_final=None,
        nif_emisor="B12345678",
        nif_cliente="A87654321",
        num_factura="FAC-2026-000099",
        fecha_emision="2026-03-24",
        total_factura=242.0,
        tipo_factura="F1",
    )
    assert prev is None
    assert len(fp) == 64
    expected = VerifactuService.generar_hash_factura(
        nif_empresa="B12345678",
        nif_cliente="A87654321",
        num_factura="FAC-2026-000099",
        fecha="2026-03-24",
        total=242.0,
        hash_anterior=VERIFACTU_CHAIN_SEED_HEX,
        tipo_factura=None,
    )
    assert fp == expected


def test_fingerprint_desde_eslabon_enlaza_hash_previo() -> None:
    prev_hex = "ab" * 32
    fp, prev_out = VerifactuService.fingerprint_desde_eslabon_finalizado(
        prev_fingerprint_final=prev_hex,
        nif_emisor="B1",
        nif_cliente="C1",
        num_factura="FAC-2026-000100",
        fecha_emision="2026-03-24",
        total_factura=50.0,
    )
    assert prev_out == prev_hex
    exp = VerifactuService.generar_hash_factura(
        nif_empresa="B1",
        nif_cliente="C1",
        num_factura="FAC-2026-000100",
        fecha="2026-03-24",
        total=50.0,
        hash_anterior=prev_hex,
    )
    assert fp == exp


def test_build_tike_url_incluye_huella() -> None:
    u = build_tike_verifactu_url("B1", "F-1", "2026-03-24", 10.0, huella="cc" * 32)
    assert "huella=" in u
    assert "TIKE-CONT/ValidarQR" in u


def test_build_srei_url_verifactu_parametros() -> None:
    u = build_srei_verifactu_url("B12345678", "FAC-2026-000001", "2026-03-24", 121.0)
    assert "vlz/SREI/VERIFACTU" in u
    assert "nif=B12345678" in u
    assert "numser=FAC-2026-000001" in u
    assert "fec=24-03-2026" in u
    assert "imp=121.00" in u


@pytest.mark.asyncio
async def test_generate_aeat_url_desde_factura() -> None:
    eid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    factura = {
        "id": 42,
        "empresa_id": eid,
        "nif_emisor": "B12345678",
        "num_factura": "FAC-2026-000001",
        "fecha_emision": "2026-03-24",
        "total_factura": 121.0,
    }

    # ``SupabaseAsync.execute(query)``: el mock solo debe devolver datos en ``execute``.
    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(data=[factura]))
    db.table = MagicMock(
        return_value=MagicMock(
            select=MagicMock(
                return_value=MagicMock(
                    eq=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=object())))
                )
            )
        )
    )

    svc = VerifactuService(db)
    url = await svc.generate_aeat_url(42)
    assert "vlz/SREI/VERIFACTU" in url
    assert "nif=B12345678" in url
