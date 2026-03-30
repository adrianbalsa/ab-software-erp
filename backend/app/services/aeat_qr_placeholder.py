"""Generación de QR AEAT para VeriFactu."""

from __future__ import annotations

from urllib.parse import urlencode


def generate_aeat_qr(
    nif: str,
    num_factura: str,
    fecha: str,
    importe: float,
    hash_factura: str,
) -> str:
    """
    Genera la URL estándar AEAT para el QR VeriFactu.
    
    URL: https://www2.agenciatributaria.gob.es/wlpl/VERI-FACTU/Consulta
    
    Args:
        nif: NIF del emisor
        num_factura: Número de factura (Serie-Año-Secuencial)
        fecha: Fecha de emisión (YYYY-MM-DD)
        importe: Importe total de la factura
        hash_factura: Hash SHA-256 de la factura
        
    Returns:
        URL completa para el QR VeriFactu
    """
    base_url = "https://www2.agenciatributaria.gob.es/wlpl/VERI-FACTU/Consulta"
    
    params = {
        "nif": nif,
        "num": num_factura,
        "fecha": fecha,
        "importe": f"{importe:.2f}",
        "hash": hash_factura,
    }
    
    query_string = urlencode(params)
    
    return f"{base_url}?{query_string}"

