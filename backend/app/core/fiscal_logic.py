"""Lógica fiscal para VeriFactu: encadenamiento de facturas y firmas digitales."""

from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

GENESIS_HASH = "0" * 64


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


def compute_invoice_fingerprint(invoice_data: dict[str, Any], prev_hash: str) -> str:
    """
    Calcula la huella digital SHA-256 de una factura según normativa VeriFactu.
    
    Concatenación: ID_Emisor + ID_Receptor + NumeroFactura + Fecha + ImporteTotal + prev_hash
    
    Args:
        invoice_data: Diccionario con campos:
            - id_emisor o nif_emisor: NIF del emisor
            - id_receptor o nif_receptor: NIF del receptor
            - numero_factura o num_factura: Número de factura
            - fecha_emision o fecha: Fecha de emisión
            - importe_total o total_factura: Importe total
        prev_hash: Hash de la factura anterior (GENESIS_HASH si es la primera)
    
    Returns:
        Hash SHA-256 en formato hexadecimal (64 caracteres)
    """
    id_emisor = str(
        invoice_data.get("id_emisor") 
        or invoice_data.get("nif_emisor") 
        or ""
    ).strip()
    
    id_receptor = str(
        invoice_data.get("id_receptor") 
        or invoice_data.get("nif_receptor") 
        or ""
    ).strip()
    
    numero_factura = str(
        invoice_data.get("numero_factura") 
        or invoice_data.get("num_factura") 
        or ""
    ).strip()
    
    fecha = str(
        invoice_data.get("fecha_emision") 
        or invoice_data.get("fecha") 
        or ""
    ).strip()
    
    importe_total_str = fiscal_amount_string_two_decimals(
        invoice_data.get("importe_total") or invoice_data.get("total_factura")
    )
    
    prev = str(prev_hash or "").strip() or GENESIS_HASH
    
    payload = f"{id_emisor}|{id_receptor}|{numero_factura}|{fecha}|{importe_total_str}|{prev}"
    
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
