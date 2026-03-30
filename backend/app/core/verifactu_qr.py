from __future__ import annotations

from typing import Any

from app.services.aeat_qr_service import build_srei_verifactu_url, qr_png_bytes_from_url


def _srei_fields_from_invoice(invoice_data: dict[str, Any]) -> tuple[str, str, str, float]:
    """Normalización única para URL SREI y QR (importe con 2 decimales vía build_srei_verifactu_url)."""
    nif = str(invoice_data.get("nif_emisor") or "").strip()
    num = str(
        invoice_data.get("num_factura")
        or invoice_data.get("numero_factura")
        or ""
    ).strip()
    fecha = str(
        invoice_data.get("fecha_expedicion") or invoice_data.get("fecha_emision") or ""
    ).strip()
    try:
        importe = float(invoice_data.get("importe_total") or invoice_data.get("total_factura") or 0.0)
    except (TypeError, ValueError):
        importe = 0.0
    return nif, num, fecha, importe


def generate_verifactu_qr_with_url(invoice_data: dict[str, Any]) -> tuple[bytes, str]:
    """
    PNG del QR y la misma cadena URL codificada en el QR (SREI, importe ``.2f`` con punto).
    """
    nif, num, fecha, importe = _srei_fields_from_invoice(invoice_data)
    url = build_srei_verifactu_url(nif, num, fecha, importe)
    return qr_png_bytes_from_url(url), url


def generate_verifactu_qr(invoice_data: dict[str, Any]) -> bytes:
    """
    Genera QR PNG de cotejo AEAT para factura VeriFactu.

    Requiere: NIF emisor, número de factura, fecha de expedición e importe total.
    """
    return generate_verifactu_qr_with_url(invoice_data)[0]
