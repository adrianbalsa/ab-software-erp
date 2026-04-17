from __future__ import annotations

import hashlib
from typing import Any

from app.core.fiscal_logic import fiscal_amount_string_two_decimals

GENESIS_HASH = "0" * 64


def generate_invoice_hash(invoice_data: dict[str, Any], previous_hash: str) -> str:
    """
    Encadenamiento de integridad para factura (SHA-256).

    Cadena base:
    ID Factura + Fecha/Hora + Emisor + Receptor + Importe Total + Hash previo
    """
    factura_id = str(
        invoice_data.get("factura_id")
        or invoice_data.get("num_factura")
        or invoice_data.get("numero_factura")
        or ""
    ).strip()
    fecha_hora = str(
        invoice_data.get("fecha_hora")
        or invoice_data.get("fecha_emision")
        or invoice_data.get("fecha")
        or ""
    ).strip()
    emisor = str(invoice_data.get("emisor") or invoice_data.get("nif_emisor") or "").strip()
    receptor = str(invoice_data.get("receptor") or invoice_data.get("nif_receptor") or "").strip()
    total_norm = fiscal_amount_string_two_decimals(
        invoice_data.get("importe_total") or invoice_data.get("total_factura")
    )

    prev = str(previous_hash or "").strip() or GENESIS_HASH
    payload = f"{factura_id}|{fecha_hora}|{emisor}|{receptor}|{total_norm}|{prev}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_invoice_chain(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Verifica integridad de cadena ``fingerprint_hash`` en orden cronológico.
    """
    previous = GENESIS_HASH
    total_verified = 0

    for invoice in invoices:
        factura_id = invoice.get("id")
        stored_hash = str(invoice.get("fingerprint_hash") or "").strip()
        stored_prev = str(invoice.get("previous_fingerprint") or "").strip() or GENESIS_HASH
        if not stored_hash:
            return {
                "is_valid": False,
                "total_verified": total_verified,
                "factura_id": factura_id,
                "error": "Factura sin fingerprint_hash",
            }
        if stored_prev != previous:
            return {
                "is_valid": False,
                "total_verified": total_verified,
                "factura_id": factura_id,
                "error": "previous_fingerprint no coincide con eslabón anterior",
            }

        recalculated = generate_invoice_hash(
            {
                "factura_id": invoice.get("numero_factura") or invoice.get("num_factura") or factura_id,
                "fecha_hora": invoice.get("fecha_emision"),
                "emisor": invoice.get("nif_emisor"),
                "receptor": invoice.get("nif_receptor") or invoice.get("nif_cliente"),
                "importe_total": invoice.get("total_factura"),
            },
            previous,
        )
        if recalculated != stored_hash:
            return {
                "is_valid": False,
                "total_verified": total_verified,
                "factura_id": factura_id,
                "error": "fingerprint_hash recalculado no coincide",
            }

        previous = stored_hash
        total_verified += 1

    return {
        "is_valid": True,
        "total_verified": total_verified,
        "factura_id": None,
        "error": None,
    }
