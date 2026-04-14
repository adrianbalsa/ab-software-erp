"""
Utilidades de auditoría y diagnóstico para desincronización de la cadena VeriFactu.

No reescribe datos en BD: solo analiza y propone acciones para revisión humana.
"""

from __future__ import annotations

from typing import Any

from app.core.verifactu import GENESIS_HASH, generate_invoice_hash
from app.core.fiscal_logic import compute_invoice_fingerprint


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
        expected_fp = compute_invoice_fingerprint(inv, prev_fp)
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
) -> list[str]:
    """
    Mensajes de alto nivel para auditoría (sin SQL automático).
    """
    out: list[str] = []
    d = db_discrepancies or []
    if d:
        out.append(
            f"Se detectaron {len(d)} discrepancia(s) en hash_factura / hash_anterior "
            "respecto al recálculo. Revisar facturas listadas y, si procede, "
            "abrir incidencia con copia de seguridad de la BD antes de cualquier corrección manual."
        )
    fh = fingerprint_hash_report or {}
    if not fh.get("ok"):
        for issue in fh.get("issues") or []:
            if issue.get("tipo") == "previous_fingerprint":
                out.append(
                    "Cadena de `previous_fingerprint`: posible factura insertada fuera de orden "
                    "o rollback parcial. Revisar secuencia `numero_secuencial` y bloqueos "
                    "(`bloqueado = true`) por empresa."
                )
                break
    if not out:
        out.append("Sin anomalías detectadas en los informes recibidos.")
    return out
