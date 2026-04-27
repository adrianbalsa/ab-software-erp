"""Cierre DD: cadena fingerprint, materialización NIF y configuración de series."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.crypto import pii_crypto
from app.core.verifactu import verify_invoice_chain
from app.core.verifactu_hashing import VerifactuCadena, generar_hash_factura_oficial
from app.services.verifactu_fingerprint_audit import materialize_factura_rows_for_fingerprint_verify

TEST_GENESIS_HASH = "11" * 32


def test_settings_exposes_verifactu_series() -> None:
    s = get_settings()
    assert s.VERIFACTU_SERIE_FACTURA.strip()
    assert s.VERIFACTU_SERIE_RECTIFICATIVA.strip()


def test_verify_invoice_chain_valid_two_invoices() -> None:
    g = TEST_GENESIS_HASH
    h1 = generar_hash_factura_oficial(
        VerifactuCadena.HUELLA_FINGERPRINT,
        {
            "nif_emisor": "B11111111",
            "nif_receptor": "A22222222",
            "numero_factura": "FAC-2026-000001",
            "fecha_emision": "2026-01-15",
            "total_factura": 121.0,
        },
        g,
    )
    h2 = generar_hash_factura_oficial(
        VerifactuCadena.HUELLA_FINGERPRINT,
        {
            "nif_emisor": "B11111111",
            "nif_receptor": "A22222222",
            "numero_factura": "FAC-2026-000002",
            "fecha_emision": "2026-01-16",
            "total_factura": 50.0,
        },
        h1,
    )
    rows = [
        {
            "id": 1,
            "numero_factura": "FAC-2026-000001",
            "num_factura": "FAC-2026-000001",
            "fecha_emision": "2026-01-15",
            "nif_emisor": "B11111111",
            "nif_receptor": "A22222222",
            "total_factura": 121.0,
            "fingerprint_hash": h1,
            "previous_fingerprint": g,
        },
        {
            "id": 2,
            "numero_factura": "FAC-2026-000002",
            "num_factura": "FAC-2026-000002",
            "fecha_emision": "2026-01-16",
            "nif_emisor": "B11111111",
            "nif_receptor": "A22222222",
            "total_factura": 50.0,
            "fingerprint_hash": h2,
            "previous_fingerprint": h1,
        },
    ]
    r = verify_invoice_chain(rows, genesis_hash=g)
    assert r["is_valid"] is True
    assert r["total_verified"] == 2
    assert r.get("error") is None


def test_materialize_decrypts_emisor_and_fills_receptor_from_map() -> None:
    cid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    enc = pii_crypto.encrypt_pii("B33333333")
    assert enc
    rows = [
        {
            "id": 1,
            "cliente": cid,
            "nif_emisor": enc,
            "numero_factura": "FAC-2026-000099",
            "fecha_emision": "2026-02-01",
            "total_factura": 10.0,
            "fingerprint_hash": "00",
            "previous_fingerprint": TEST_GENESIS_HASH,
        }
    ]
    m = materialize_factura_rows_for_fingerprint_verify(
        rows, cliente_nif_map={cid: "J44444444"}
    )
    assert m[0]["nif_emisor"] == "B33333333"
    assert m[0]["nif_receptor"] == "J44444444"
