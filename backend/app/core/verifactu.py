from __future__ import annotations

from typing import Any

from app.core.i18n import get_translator
from app.core.verifactu_hashing import (
    VERIFACTU_INVOICE_GENESIS_HASH,
    VerifactuCadena,
    generar_hash_factura_oficial,
)

GENESIS_HASH = VERIFACTU_INVOICE_GENESIS_HASH

ERR_MISSING_FINGERPRINT = "VF_MISSING_FINGERPRINT_HASH"
ERR_PREV_MISMATCH = "VF_PREVIOUS_FINGERPRINT_MISMATCH"
ERR_HASH_MISMATCH = "VF_FINGERPRINT_HASH_MISMATCH"


def verify_invoice_chain(
    invoices: list[dict[str, Any]],
    *,
    lang: str | None = None,
) -> dict[str, Any]:
    """
    Verifica integridad de cadena ``fingerprint_hash`` en orden cronológico.

    Recalcula con ``generar_hash_factura_oficial`` (``HUELLA_FINGERPRINT``), misma lógica que al emitir.

    ``error`` / ``error_message`` dependen de ``lang`` (``es`` | ``en``). ``error_code`` es estable para automatismos.
    """
    t = get_translator(lang)
    previous = GENESIS_HASH
    total_verified = 0

    for invoice in invoices:
        factura_id = invoice.get("id")
        stored_hash = str(invoice.get("fingerprint_hash") or "").strip()
        stored_prev = str(invoice.get("previous_fingerprint") or "").strip() or GENESIS_HASH
        if not stored_hash:
            msg = t("VeriFactu chain: invoice has no fingerprint_hash")
            return {
                "is_valid": False,
                "total_verified": total_verified,
                "factura_id": factura_id,
                "error": msg,
                "error_message": msg,
                "error_code": ERR_MISSING_FINGERPRINT,
            }
        if stored_prev != previous:
            msg = t("VeriFactu chain: previous_fingerprint does not match prior link")
            return {
                "is_valid": False,
                "total_verified": total_verified,
                "factura_id": factura_id,
                "error": msg,
                "error_message": msg,
                "error_code": ERR_PREV_MISMATCH,
            }

        recalculated = generar_hash_factura_oficial(
            VerifactuCadena.HUELLA_FINGERPRINT,
            {
                "nif_emisor": invoice.get("nif_emisor"),
                "nif_receptor": invoice.get("nif_receptor") or invoice.get("nif_cliente"),
                "numero_factura": invoice.get("numero_factura") or invoice.get("num_factura") or factura_id,
                "fecha_emision": invoice.get("fecha_emision"),
                "total_factura": invoice.get("total_factura"),
            },
            previous,
        )
        if recalculated != stored_hash:
            msg = t("VeriFactu chain: recalculated fingerprint_hash does not match stored value")
            return {
                "is_valid": False,
                "total_verified": total_verified,
                "factura_id": factura_id,
                "error": msg,
                "error_message": msg,
                "error_code": ERR_HASH_MISMATCH,
            }

        previous = stored_hash
        total_verified += 1

    return {
        "is_valid": True,
        "total_verified": total_verified,
        "factura_id": None,
        "error": None,
        "error_message": None,
        "error_code": None,
    }
