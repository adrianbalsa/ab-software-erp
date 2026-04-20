"""
Huellas criptográficas VeriFactu — **único punto de verdad** para cadenas persistidas.

- ``HUELLA_EMISION``: ``hash_registro`` / ``hash_factura`` / ``huella_hash`` (pipe + NIF normalizado).
- ``HUELLA_FINGERPRINT``: columnas ``fingerprint_hash`` / ``previous_fingerprint`` (orden legado AEAT-adjunto).
"""

from __future__ import annotations

import datetime
import hashlib
import re
from enum import StrEnum
from typing import Any

from app.core.fiscal_logic import fiscal_amount_string_two_decimals

VERIFACTU_INVOICE_GENESIS_HASH = "0" * 64

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class VerifactuCadena(StrEnum):
    """Variante de cadena previa a SHA-256 (misma génesis ``0``×64, distinto payload)."""

    HUELLA_EMISION = "huella_emision"
    HUELLA_FINGERPRINT = "huella_fingerprint"


def _norm_str(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm_nif_emision(value: Any) -> str:
    return "".join(_norm_str(value).split()).upper()


def _norm_fecha_emision(value: Any) -> str:
    raw = _norm_str(value)
    if len(raw) >= 10 and _ISO_DATE_RE.match(raw):
        return raw[:10]
    try:
        if isinstance(value, datetime.datetime):
            return value.date().isoformat()
        if isinstance(value, datetime.date):
            return value.isoformat()
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(raw[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def generar_hash_factura_oficial(
    cadena: VerifactuCadena,
    invoice_data: dict[str, Any],
    previous_hash: str | None,
) -> str:
    """
    SHA-256 hexadecimal (64 caracteres) para la cadena VeriFactu indicada.

    ``previous_hash`` vacío o ``None`` implica ``VERIFACTU_INVOICE_GENESIS_HASH``.
    """
    prev = str(previous_hash or "").strip()
    if not prev:
        prev = VERIFACTU_INVOICE_GENESIS_HASH

    if cadena == VerifactuCadena.HUELLA_EMISION:
        num = _norm_str(invoice_data.get("num_factura") or invoice_data.get("numero_factura"))
        fecha = _norm_fecha_emision(invoice_data.get("fecha_emision") or invoice_data.get("fecha"))
        nif_e = _norm_nif_emision(invoice_data.get("nif_emisor") or invoice_data.get("nif_empresa"))
        tot = fiscal_amount_string_two_decimals(
            invoice_data.get("total_factura")
            if invoice_data.get("total_factura") is not None
            else invoice_data.get("total")
        )
        payload = f"{num}|{fecha}|{nif_e}|{tot}|{prev}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # HUELLA_FINGERPRINT — misma semántica que el antiguo ``compute_invoice_fingerprint`` (sin tocar NIFs).
    id_emisor = str(
        invoice_data.get("id_emisor") or invoice_data.get("nif_emisor") or ""
    ).strip()
    id_receptor = str(
        invoice_data.get("id_receptor") or invoice_data.get("nif_receptor") or ""
    ).strip()
    numero_factura = str(
        invoice_data.get("numero_factura") or invoice_data.get("num_factura") or ""
    ).strip()
    fecha_fp = str(
        invoice_data.get("fecha_emision") or invoice_data.get("fecha") or ""
    ).strip()
    importe_total_str = fiscal_amount_string_two_decimals(
        invoice_data.get("importe_total") or invoice_data.get("total_factura")
    )
    payload = f"{id_emisor}|{id_receptor}|{numero_factura}|{fecha_fp}|{importe_total_str}|{prev}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
