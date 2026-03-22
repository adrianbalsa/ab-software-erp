"""
Código QR VeriFactu (URL de verificación AEAT).
"""

from __future__ import annotations

import base64
import io
import re
from urllib.parse import quote

import qrcode

_QR_BASE_URL = (
    "https://www2.agenciatributaria.gob.es/wlpl/inwinv/es/zs/iva/verifactu"
)


def _fecha_para_qr(fecha: str) -> str:
    """
    Normaliza a DD-MM-AAAA (habitual en parámetros de verificación AEAT).
    Acepta ISO ``YYYY-MM-DD`` o texto ya en ``DD-MM-AAAA``.
    """
    raw = (fecha or "").strip()
    if not raw:
        return ""
    if re.match(r"^\d{2}-\d{2}-\d{4}$", raw):
        return raw
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        y, m, d = raw[:10].split("-")
        return f"{d}-{m}-{y}"
    return raw[:10]


def _importe_para_qr(importe_total: float) -> str:
    return f"{float(importe_total):.2f}"


def generar_qr_verifactu(
    nif_emisor: str,
    num_factura: str,
    fecha: str,
    importe_total: float,
) -> str:
    """
    Genera un QR PNG codificado en **base64** (ASCII) para incrustar en PDF u HTML.

    La URL sigue el patrón indicado por la AEAT para consulta de factura:
    ``...?nif=...&num=...&fecha=...&importe=...`` (query escapada).
    """
    nif = (nif_emisor or "").strip()
    num = (num_factura or "").strip()
    fe = _fecha_para_qr(fecha)
    imp = _importe_para_qr(importe_total)

    q = (
        f"nif={quote(nif, safe='')}"
        f"&num={quote(num, safe='')}"
        f"&fecha={quote(fe, safe='')}"
        f"&importe={quote(imp, safe='')}"
    )
    url = f"{_QR_BASE_URL}?{q}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")

