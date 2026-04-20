"""
Auditoría de cadena ``fingerprint_hash``: NIF emisor cifrado en reposo y NIF receptor
solo en tabla ``clientes`` — materializar filas antes de ``verify_invoice_chain`` /
``diagnose_fingerprint_hash_chain``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.crypto import pii_crypto
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync

logger = logging.getLogger(__name__)

_CHUNK = 100


async def load_cliente_nif_map_for_facturas(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    """``cliente_id`` → NIF (texto) para filas de ``facturas`` con ``cliente`` / ``cliente_id``."""
    eid = str(empresa_id or "").strip()
    ids: set[str] = set()
    for r in rows:
        cid = str(r.get("cliente") or r.get("cliente_id") or "").strip()
        if cid:
            ids.add(cid)
    if not ids or not eid:
        return {}
    out: dict[str, str] = {}
    id_list = list(ids)
    for i in range(0, len(id_list), _CHUNK):
        chunk = id_list[i : i + _CHUNK]
        try:
            q = filter_not_deleted(
                db.table("clientes").select("id,nif").eq("empresa_id", eid).in_("id", chunk)
            )
            res = await db.execute(q)
            for row in (res.data or []) if hasattr(res, "data") else []:
                kid = str(row.get("id") or "").strip()
                nif = str(row.get("nif") or "").strip()
                if kid:
                    out[kid] = nif
        except Exception:
            logger.exception("load_cliente_nif_map_for_facturas chunk failed empresa_id=%s", eid)
    return out


def materialize_factura_rows_for_fingerprint_verify(
    rows: list[dict[str, Any]],
    *,
    cliente_nif_map: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Copia superficial con ``nif_emisor`` descifrado y ``nif_receptor`` rellenado desde el mapa si falta.
    """
    materialized: list[dict[str, Any]] = []
    for r in rows:
        m = dict(r)
        raw_e = m.get("nif_emisor")
        if raw_e is not None:
            s = str(raw_e).strip()
            dec = pii_crypto.decrypt_pii(s)
            m["nif_emisor"] = (dec if dec is not None else "") or s
        cid = str(m.get("cliente") or m.get("cliente_id") or "").strip()
        if cid and not str(m.get("nif_receptor") or m.get("nif_cliente") or "").strip():
            cn = cliente_nif_map.get(cid, "")
            if cn:
                m["nif_receptor"] = cn
        materialized.append(m)
    return materialized
