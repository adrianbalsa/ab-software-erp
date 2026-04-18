"""
Construcción de XML de alta VeriFactu (bloques lógicos Cabecera, RegistroFactura, Desglose).

El envío oficial con SOAP+mTLS y **firma XAdES-BES** del registro se implementa en
``app.services.verifactu_sender`` (payload **SuministroLR** vía
``app.services.suministro_lr_xml`` / ``generar_xml_registro_facturacion_alta``).
Este módulo conserva un generador ``VeriFactuAlta`` legado solo para persistencia
histórica en inserciones que aún llaman ``generar_xml_alta_factura``.
"""

from __future__ import annotations

import io
import json
from decimal import Decimal
from typing import Any, Mapping
from xml.etree import ElementTree as ET

from app.core.fiscal_logic import fiscal_amount_string_two_decimals
from app.core.math_engine import RECARGO_EQUIVALENCIA_POR_IVA_PCT, quantize_financial


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
        ``nif_emisor``, ``factura_rectificada_id``, ``motivo_rectificacion``,
        opcional ``desglose_por_tipo`` (lista o JSON) alineado con Math Engine.
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

    total = fiscal_amount_string_two_decimals(factura.get("total_factura"))

    tipo = str(factura.get("tipo_factura") or "F1").strip().upper() or "F1"
    nif_emisor = str(factura.get("nif_emisor") or empresa.get("nif") or "").strip()
    nif_dest = str(cliente.get("nif") or "").strip()

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
    _txt(reg, "ImporteTotal", total)
    _txt(reg, "HashRegistro", str(hash_registro).strip())

    rect_id = factura.get("factura_rectificada_id")
    if rect_id is not None:
        _txt(reg, "FacturaRectificadaId", str(rect_id).strip())
    motivo = factura.get("motivo_rectificacion")
    if motivo:
        _txt(reg, "MotivoRectificacion", str(motivo).strip()[:500])

    raw_des = factura.get("desglose_por_tipo")
    if isinstance(raw_des, str) and raw_des.strip():
        try:
            raw_des = json.loads(raw_des)
        except json.JSONDecodeError:
            raw_des = None

    if isinstance(raw_des, list) and len(raw_des) > 0:
        for block in raw_des[:12]:
            if not isinstance(block, Mapping):
                continue
            des = ET.SubElement(root, "DesgloseIVA")
            base = fiscal_amount_string_two_decimals(block.get("base_imponible"))
            cuota = fiscal_amount_string_two_decimals(block.get("cuota_iva"))
            _txt(des, "BaseImponible", base)
            _txt(des, "CuotaIVA", cuota)
            tipo_pct = block.get("tipo_iva_porcentaje")
            if tipo_pct is not None and str(tipo_pct).strip() != "":
                _txt(des, "TipoImpositivo", fiscal_amount_string_two_decimals(tipo_pct))
            cre = block.get("cuota_recargo_equivalencia")
            if cre is not None and fiscal_amount_string_two_decimals(cre) not in ("0.00", "-0.00"):
                tp_re = tipo_pct
                if tp_re is None:
                    try:
                        b_blk = Decimal(str(block.get("base_imponible") or "0"))
                        c_blk = Decimal(str(block.get("cuota_iva") or "0"))
                        tp_re = (
                            quantize_financial((c_blk / b_blk) * Decimal("100"))
                            if b_blk != Decimal("0")
                            else Decimal("0.00")
                        )
                    except Exception:
                        tp_re = Decimal("0.00")
                tk = str(quantize_financial(tp_re))
                tre = RECARGO_EQUIVALENCIA_POR_IVA_PCT.get(tk, Decimal("0.00"))
                _txt(des, "TipoRecargoEquivalencia", fiscal_amount_string_two_decimals(tre))
                _txt(des, "CuotaRecargoEquivalencia", fiscal_amount_string_two_decimals(cre))
            tns = str(block.get("tipo_no_sujecion") or "").strip()
            if tns:
                _txt(des, "TipoNoSujecion", tns)
            mex = str(block.get("motivo_exencion") or "").strip()
            if mex:
                _txt(des, "CausaExencion", mex)
            irpf = block.get("cuota_retencion_irpf")
            if irpf is not None and fiscal_amount_string_two_decimals(irpf) not in ("0.00", "-0.00"):
                _txt(des, "CuotaRetencionIRPF", fiscal_amount_string_two_decimals(irpf))
    else:
        base = fiscal_amount_string_two_decimals(factura.get("base_imponible"))
        cuota = fiscal_amount_string_two_decimals(factura.get("cuota_iva"))
        tipo_iva_pct = None
        try:
            b_dec = Decimal(str(factura.get("base_imponible") or "0"))
            c_dec = Decimal(str(factura.get("cuota_iva") or "0"))
            if b_dec != Decimal("0"):
                tipo_iva_pct = fiscal_amount_string_two_decimals((c_dec / b_dec) * Decimal("100"))
        except Exception:
            tipo_iva_pct = None

        des = ET.SubElement(root, "Desglose")
        _txt(des, "BaseImponible", base)
        _txt(des, "CuotaIVA", cuota)
        if tipo_iva_pct is not None:
            _txt(des, "TipoImpositivo", tipo_iva_pct)
        re_cu = factura.get("cuota_recargo_equivalencia")
        if re_cu is not None and fiscal_amount_string_two_decimals(re_cu) not in ("0.00", "-0.00"):
            tp_src = factura.get("tipo_iva_porcentaje") or factura.get("iva_porcentaje")
            if tp_src is not None:
                tk = str(quantize_financial(tp_src))
            else:
                try:
                    b0 = Decimal(str(factura.get("base_imponible") or "0"))
                    c0 = Decimal(str(factura.get("cuota_iva") or "0"))
                    tk = str(
                        quantize_financial((c0 / b0) * Decimal("100"))
                        if b0 != Decimal("0")
                        else Decimal("0.00")
                    )
                except Exception:
                    tk = "0.00"
            tre = RECARGO_EQUIVALENCIA_POR_IVA_PCT.get(tk, Decimal("0.00"))
            _txt(des, "TipoRecargoEquivalencia", fiscal_amount_string_two_decimals(tre))
            _txt(des, "CuotaRecargoEquivalencia", fiscal_amount_string_two_decimals(re_cu))
        irpf = factura.get("cuota_retencion_irpf")
        if irpf is not None and fiscal_amount_string_two_decimals(irpf) not in ("0.00", "-0.00"):
            _txt(des, "CuotaRetencionIRPF", fiscal_amount_string_two_decimals(irpf))

    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")
