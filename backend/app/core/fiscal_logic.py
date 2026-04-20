"""Lógica fiscal para VeriFactu: encadenamiento de facturas y firmas digitales."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

def fiscal_amount_string_two_decimals(value: Any) -> str:
    """
    Cadena de importe con exactamente dos decimales (ROUND_HALF_EVEN), sin pasar por ``float``,
    para huellas VeriFactu y nodos ``Importe*`` / ``Cuota*`` en XML AEAT (coherencia con XAdES).
    """
    try:
        if value is None:
            d = Decimal("0.00")
        elif isinstance(value, Decimal):
            d = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        else:
            d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError, TypeError):
        d = Decimal("0.00")
    return f"{d:.2f}"

# Tolerancia contable estándar para redondeos IVA (céntimos).
DEFAULT_TOTAL_TOLERANCE_EUR = Decimal("0.01")


def totals_coherent(
    base_imponible: float | Decimal | None,
    cuota_iva: float | Decimal | None,
    total_factura: float | Decimal | None,
    *,
    tolerance_eur: Decimal = DEFAULT_TOTAL_TOLERANCE_EUR,
) -> bool:
    """
    Comprueba Base + IVA ≈ Total con tolerancia (p. ej. 0,01 € por redondeo).

    Usar **antes** de sellar hash o firmar; no sustituye al motor fiscal principal.
    """
    try:
        b = Decimal(str(base_imponible or 0))
        c = Decimal(str(cuota_iva or 0))
        t = Decimal(str(total_factura or 0))
    except Exception:
        return False
    expected = (b + c).quantize(Decimal("0.01"))
    got = t.quantize(Decimal("0.01"))
    return abs(expected - got) <= tolerance_eur


def sign_invoice_xades(invoice_xml: str, certificate_path: str) -> str:
    """
    Aplica firma digital XAdES-BES al XML de factura según especificaciones AEAT.
    
    Args:
        invoice_xml: XML de la factura en formato string
        certificate_path: Ruta al certificado digital (PEM)
    
    Returns:
        XML firmado con XAdES-BES
    """
    from pathlib import Path
    from app.core.xades_signer import sign_xml_xades
    
    cert_path = Path(certificate_path)
    key_path = cert_path.parent / f"{cert_path.stem}_key.pem"
    
    with open(cert_path, "rb") as f:
        cert_pem = f.read()
    
    with open(key_path, "rb") as f:
        key_pem = f.read()
    
    xml_bytes = invoice_xml.encode("utf-8")
    
    signed_xml_bytes = sign_xml_xades(
        xml_bytes=xml_bytes,
        cert_pem=cert_pem,
        key_pem=key_pem,
        password=None,
    )
    
    return signed_xml_bytes.decode("utf-8")
