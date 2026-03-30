"""
Construcción de XML de alta VeriFactu (bloques lógicos Cabecera, RegistroFactura, Desglose).

El envío oficial con SOAP+mTLS y **firma XAdES-BES** del registro se implementa en
``app.services.verifactu_sender`` (misma estructura lógica ampliada en
``generar_xml_registro_facturacion_alta``). Este módulo conserva un generador
``VeriFactuAlta`` legado; nuevas integraciones deberían alinearse con el sender.
"""

from __future__ import annotations

import io
from typing import Any, Mapping
from xml.etree import ElementTree as ET


def _txt(parent: ET.Element, tag: str, value: Any) -> None:
    el = ET.SubElement(parent, tag)
    if value is None:
        el.text = ""
    else:
        el.text = str(value).strip()


def generar_xml_alta_factura(
    factura: Mapping[str, Any],
    empresa: Mapping[str, Any],
    cliente: Mapping[str, Any],
    hash_registro: str,
) -> str:
    """
    Genera XML UTF-8 con cabecera, registro de factura (huella) y desglose de IVA.

    Parameters
    ----------
    factura:
        Campos típicos: ``num_factura`` / ``numero_factura``, ``fecha_emision``,
        ``base_imponible``, ``cuota_iva``, ``total_factura``, ``tipo_factura``,
        ``nif_emisor``, ``factura_rectificada_id``, ``motivo_rectificacion``.
    empresa:
        ``nif``, ``nombre_comercial`` / ``nombre_legal``.
    cliente:
        ``nif``, ``nombre``.
    hash_registro:
        Huella SHA-256 hex del encadenamiento VeriFactu.
    """
    num = str(
        factura.get("num_factura")
        or factura.get("numero_factura")
        or ""
    ).strip()
    fecha = str(factura.get("fecha_emision") or "").strip()
    if len(fecha) >= 10:
        fecha = fecha[:10]

    try:
        base = float(factura.get("base_imponible") or 0.0)
    except (TypeError, ValueError):
        base = 0.0
    try:
        cuota = float(factura.get("cuota_iva") or 0.0)
    except (TypeError, ValueError):
        cuota = 0.0
    try:
        total = float(factura.get("total_factura") or 0.0)
    except (TypeError, ValueError):
        total = 0.0

    tipo = str(factura.get("tipo_factura") or "F1").strip().upper() or "F1"
    nif_emisor = str(factura.get("nif_emisor") or empresa.get("nif") or "").strip()
    nif_dest = str(cliente.get("nif") or "").strip()

    tipo_iva_pct = None
    if base and abs(base) > 1e-9:
        try:
            tipo_iva_pct = round((cuota / base) * 100.0, 2)
        except (ZeroDivisionError, TypeError, ValueError):
            tipo_iva_pct = None

    nombre_emisor = str(
        empresa.get("nombre_comercial") or empresa.get("nombre_legal") or ""
    ).strip()
    nombre_dest = str(cliente.get("nombre") or "").strip()

    root = ET.Element("VeriFactuAlta")
    root.set("versionFormato", "1.0")

    cab = ET.SubElement(root, "Cabecera")
    _txt(cab, "IdVersion", "1.0")
    _txt(cab, "NIFEmisor", nif_emisor)
    _txt(cab, "NombreEmisor", nombre_emisor or nif_emisor)

    reg = ET.SubElement(root, "RegistroFactura")
    _txt(reg, "NumeroFactura", num)
    _txt(reg, "FechaExpedicion", fecha)
    _txt(reg, "TipoFactura", tipo)
    _txt(reg, "NIFDestinatario", nif_dest)
    _txt(reg, "NombreDestinatario", nombre_dest or nif_dest)
    _txt(reg, "ImporteTotal", f"{total:.2f}")
    _txt(reg, "HashRegistro", str(hash_registro).strip())

    rect_id = factura.get("factura_rectificada_id")
    if rect_id is not None:
        _txt(reg, "FacturaRectificadaId", str(rect_id).strip())
    motivo = factura.get("motivo_rectificacion")
    if motivo:
        _txt(reg, "MotivoRectificacion", str(motivo).strip()[:500])

    des = ET.SubElement(root, "Desglose")
    _txt(des, "BaseImponible", f"{base:.2f}")
    _txt(des, "CuotaIVA", f"{cuota:.2f}")
    if tipo_iva_pct is not None:
        _txt(des, "TipoImpositivo", f"{tipo_iva_pct:.2f}")

    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")

