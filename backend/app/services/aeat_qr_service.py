"""
Código QR VeriFactu — URL de verificación AEAT (patrón TIKE / consulta pública).
"""

from __future__ import annotations

import base64
import io
import re
from urllib.parse import quote

import qrcode

# URL pública de cotejo (modalidad factura verificable / Veri*Factu). [AEAT TIKE-CONT]
TIKE_VALIDAR_QR_BASE = (
    "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"
)

# Origen histórico del proyecto (algunos PDFs); mantener import si hace falta compat.
_QR_LEGACY_BASE = (
    "https://www2.agenciatributaria.gob.es/wlpl/inwinv/es/zs/iva/verifactu"
)

# Consulta pública VeriFactu (ruta SREI / vlz) — parámetros ``nif``, ``numser``, ``fec``, ``imp``.
SREI_VERIFACTU_BASE = (
    "https://www2.agenciatributaria.gob.es/vlz/SREI/VERIFACTU"
)


def _fecha_para_qr(fecha: str) -> str:
    """
    Normaliza a DD-MM-AAAA (parámetro ``fecha`` en consultas AEAT).
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


def _huella_corta(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    return raw[:8]


def build_srei_verifactu_url(
    nif_emisor: str,
    numserie: str,
    fecha: str,
    importe_total: float,
    huella_hash: str | None = None,
) -> str:
    """
    URL oficial de consulta VeriFactu (SREI): ``nif``, ``numser``, ``fec`` (DD-MM-AAAA), ``imp``.
    """
    nif = (nif_emisor or "").strip()
    num = (numserie or "").strip()
    fe = _fecha_para_qr(fecha)
    imp = _importe_para_qr(importe_total)
    q = (
        f"nif={quote(nif, safe='')}"
        f"&numser={quote(num, safe='')}"
        f"&fec={quote(fe, safe='')}"
        f"&imp={quote(imp, safe='')}"
    )
    hc = _huella_corta(huella_hash)
    if hc:
        q += f"&hc={quote(hc, safe='')}"
    return f"{SREI_VERIFACTU_BASE}?{q}"


def build_tike_verifactu_url(
    nif_emisor: str,
    numserie: str,
    fecha: str,
    importe_total: float,
    huella: str | None = None,
) -> str:
    """
    URL de validación TIKE con ``nif``, ``numserie``, ``fecha`` (DD-MM-AAAA), ``importe``;
    opcional ``huella`` (SHA-256 hex huella / fingerprint registral).
    """
    nif = (nif_emisor or "").strip()
    num = (numserie or "").strip()
    fe = _fecha_para_qr(fecha)
    imp = _importe_para_qr(importe_total)
    parts = [
        f"nif={quote(nif, safe='')}",
        f"numserie={quote(num, safe='')}",
        f"fecha={quote(fe, safe='')}",
        f"importe={quote(imp, safe='')}",
    ]
    h = (huella or "").strip()
    if h:
        parts.append(f"huella={quote(h, safe='')}")
    return f"{TIKE_VALIDAR_QR_BASE}?{'&'.join(parts)}"


def qr_png_bytes_from_url(url: str) -> bytes:
    """Genera PNG ISO/IEC 18004 nivel M a partir de la URL codificada."""
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
    return buf.getvalue()


def generar_qr_verifactu(
    nif_emisor: str,
    num_factura: str,
    fecha: str,
    importe_total: float,
    *,
    huella: str | None = None,
    legacy_path: bool = False,
) -> str:
    """
    QR PNG en **base64** ASCII.

    Por defecto usa TIKE ``ValidarQR``; con ``legacy_path=True`` mantiene la ruta
    ``inwinv/es/zs/iva/verifactu`` y parámetros ``num`` (compatibilidad histórica).
    """
    if legacy_path:
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
        url = f"{_QR_LEGACY_BASE}?{q}"
    else:
        url = build_tike_verifactu_url(
            nif_emisor, num_factura, fecha, importe_total, huella=huella
        )
    raw = qr_png_bytes_from_url(url)
    return base64.b64encode(raw).decode("ascii")
