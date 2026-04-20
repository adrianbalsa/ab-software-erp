"""
Utilidades de auditoría y diagnóstico para desincronización de la cadena VeriFactu.

No reescribe datos en BD: solo analiza y propone acciones para revisión humana.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import get_translator
from app.core.verifactu import GENESIS_HASH
from app.core.verifactu_hashing import VerifactuCadena, generar_hash_factura_oficial


def diagnose_fingerprint_hash_chain(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    ``rows`` ordenadas cronológicamente (p. ej. ``fecha_emision``, ``numero_secuencial``, ``id``).

    Comprueba ``previous_fingerprint`` frente al ``fingerprint_hash`` anterior **persistido**
    y recalcula cada huella con la misma función que al emitir.
    """
    if not rows:
        return {"ok": True, "issues": [], "previous_expected": GENESIS_HASH}

    issues: list[dict[str, Any]] = []
    prev_fp = GENESIS_HASH

    for row in rows:
        fid = row.get("id")
        stored_prev = str(row.get("previous_fingerprint") or "").strip() or GENESIS_HASH
        if stored_prev.lower() != prev_fp.lower():
            issues.append(
                {
                    "id": fid,
                    "tipo": "previous_fingerprint",
                    "esperado": prev_fp,
                    "almacenado": stored_prev,
                }
            )

        inv = {
            "nif_emisor": row.get("nif_emisor"),
            "nif_receptor": row.get("nif_receptor"),
            "numero_factura": row.get("numero_factura") or row.get("num_factura"),
            "fecha_emision": row.get("fecha_emision"),
            "total_factura": row.get("total_factura"),
        }
        expected_fp = generar_hash_factura_oficial(VerifactuCadena.HUELLA_FINGERPRINT, inv, prev_fp)
        stored_hash = str(row.get("fingerprint_hash") or "").strip()
        if stored_hash.lower() != expected_fp.lower():
            issues.append(
                {
                    "id": fid,
                    "tipo": "fingerprint_hash",
                    "esperado": expected_fp,
                    "almacenado": stored_hash or None,
                }
            )

        prev_fp = stored_hash if stored_hash else expected_fp

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "previous_expected": GENESIS_HASH,
    }


def repair_recommendations(
    *,
    db_discrepancies: list[dict[str, Any]] | None,
    fingerprint_hash_report: dict[str, Any] | None,
    lang: str | None = None,
) -> list[str]:
    """
    Mensajes de alto nivel para auditoría (sin SQL automático).
    """
    t = get_translator(lang)
    out: list[str] = []
    d = db_discrepancies or []
    if d:
        out.append(
            t("Audit: {n} discrepancy(ies) in hash_factura / hash_anterior vs recalculation. Review listed invoices and open an incident with a DB backup before any manual fix.").format(
                n=len(d)
            )
        )
    fh = fingerprint_hash_report or {}
    if not fh.get("ok"):
        for issue in fh.get("issues") or []:
            if issue.get("tipo") == "previous_fingerprint":
                out.append(
                    t(
                        "Audit: previous_fingerprint chain — possible out-of-order insert or partial rollback. Review numero_secuencial sequence and locks (bloqueado = true) per company."
                    )
                )
                break
    if not out:
        out.append(t("Audit: no anomalies detected in the supplied reports."))
    return out
