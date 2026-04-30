"""
Huellas criptográficas VeriFactu — **único punto de verdad** para la huella fiscal AEAT.

- ``CanonicalHashService.generate_verifactu_hash``: cadena **NIF + Número/Serie + Fecha + Importe + Huella
  anterior** (sin separadores), SHA-256 hex en **MAYÚSCULAS**.
- ``HUELLA_EMISION``: ``hash_registro`` / ``hash_factura`` / ``huella_hash`` — delega en el canónico anterior.
- ``HUELLA_FINGERPRINT``: columnas ``fingerprint_hash`` / ``previous_fingerprint`` (orden legado con pipes).
"""

from __future__ import annotations

import datetime
import hashlib
import re
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.core.fiscal_logic import fiscal_amount_string_two_decimals

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class VerifactuCadena(StrEnum):
    """Variante de cadena previa a SHA-256 (génesis resuelto por emisor, distinto payload)."""

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


# Alias públicos para servicios que reutilizan la misma normalización que la huella AEAT.
norm_nif_emisor_verifactu = _norm_nif_emision
norm_fecha_expedicion_verifactu = _norm_fecha_emision


def _norm_huella_anterior_input(value: str | None) -> str:
    t = str(value if value is not None else "").strip().upper()
    return t


def _importe_total_to_decimal_strict_no_float(value: Any) -> Decimal:
    if isinstance(value, float):
        raise TypeError(
            "importe_total must be Decimal (or int/str coercible to Decimal), not float, "
            "for VeriFactu fiscal hash determinism"
        )
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class CanonicalHashService:
    """Único punto de verdad para la huella de registro VeriFactu (cadena AEAT + SHA-256)."""

    @staticmethod
    def generate_verifactu_hash(
        nif_emisor: str,
        num_serie_factura: str,
        fecha_expedicion: str | datetime.date,
        importe_total: Decimal | int | str,
        huella_anterior: str,
    ) -> str:
        """
        SHA-256 sobre UTF-8 de: NIF + Número/Serie + Fecha (YYYY-MM-DD) + Importe (2 dec, punto) + Huella anterior.

        ``importe_total`` no admite ``float`` (``TypeError``); ``Decimal`` / ``int`` / ``str`` numérico sí.
        """
        dec = _importe_total_to_decimal_strict_no_float(importe_total)
        nif = _norm_nif_emision(nif_emisor)
        num = _norm_str(num_serie_factura)
        fecha = _norm_fecha_emision(fecha_expedicion)
        importe_str = fiscal_amount_string_two_decimals(dec)
        prev = _norm_huella_anterior_input(huella_anterior)
        if not prev:
            raise ValueError("huella_anterior vacía tras normalización")
        payload = f"{nif}{num}{fecha}{importe_str}{prev}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def generar_hash_factura_oficial(
    cadena: VerifactuCadena,
    invoice_data: dict[str, Any],
    previous_hash: str | None,
) -> str:
    """
    SHA-256 hexadecimal (64 caracteres) para la cadena VeriFactu indicada.

    ``previous_hash`` debe venir resuelto por el caller. Para la primera factura
    del emisor se usa el génesis único obtenido desde Secret Manager.
    """
    prev_stripped = str(previous_hash or "").strip()
    if not prev_stripped:
        raise ValueError("previous_hash VeriFactu vacío")
    prev_emision = _norm_huella_anterior_input(prev_stripped)

    if cadena == VerifactuCadena.HUELLA_EMISION:
        num = _norm_str(invoice_data.get("num_factura") or invoice_data.get("numero_factura"))
        fecha = _norm_fecha_emision(invoice_data.get("fecha_emision") or invoice_data.get("fecha"))
        nif_e = _norm_nif_emision(invoice_data.get("nif_emisor") or invoice_data.get("nif_empresa"))
        tot_raw = (
            invoice_data.get("total_factura")
            if invoice_data.get("total_factura") is not None
            else invoice_data.get("total")
        )
        dec = _importe_total_to_decimal_strict_no_float(tot_raw)
        return CanonicalHashService.generate_verifactu_hash(
            nif_emisor=nif_e,
            num_serie_factura=num,
            fecha_expedicion=fecha,
            importe_total=dec,
            huella_anterior=prev_emision,
        )

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
    fp_tot = invoice_data.get("importe_total")
    if fp_tot is None:
        fp_tot = invoice_data.get("total_factura")
    importe_total_str = fiscal_amount_string_two_decimals(fp_tot)
    payload = f"{id_emisor}|{id_receptor}|{numero_factura}|{fecha_fp}|{importe_total_str}|{prev_stripped}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
