"""
Construcción de XML **SuministroLR** (``RegFactuSistemaFacturacion``): ``Cabecera`` +
``RegistroFactura`` → ``RegistroAlta`` según XSD oficiales AEAT (tike/cont/ws).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any, Mapping

from lxml import etree

from app.core.fiscal_logic import fiscal_amount_string_two_decimals
from app.core.math_engine import RECARGO_EQUIVALENCIA_POR_IVA_PCT, quantize_financial


NS_LR = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroLR.xsd"
)
NS_SF = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroInformacion.xsd"
)

_EXENTAS_AEAT = {f"E{i}" for i in range(1, 9)}


def q(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _txt(parent: etree._Element, tag: str, value: Any) -> None:
    el = etree.SubElement(parent, tag)
    if value is None:
        el.text = ""
    else:
        el.text = str(value).strip()


def fecha_iso_u_otra_a_dd_mm_yyyy(fecha: str) -> str:
    """
    Tipo ``sf:fecha``: ``DD-MM-AAAA`` (10 caracteres).
    Acepta ``YYYY-MM-DD`` u otra cadena; si ya parece DD-MM-YYYY, se devuelve normalizada.
    """
    raw = str(fecha or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        y, m, d = raw[:10].split("-")
        return f"{d}-{m}-{y}"
    if len(raw) >= 10 and raw[2] == "-" and raw[5] == "-":
        return raw[:10]
    if len(raw) >= 10:
        return raw[:10]
    return "01-01-1970"


def importe_12_2(value: Any) -> str:
    """Compat: importe monetario AEAT con dos decimales (sin ``float`` intermedio)."""
    return fiscal_amount_string_two_decimals(value)


def _to_decimal_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _infer_tipo_impositivo_pct(base_d: Decimal, cuota_d: Decimal) -> Decimal | None:
    if base_d == Decimal("0"):
        return None
    try:
        return quantize_financial((cuota_d / base_d) * Decimal("100"))
    except Exception:
        return None


def _factura_desglose_rows(factura: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    Filas de desglose para ``DetalleDesglose`` (máx. 12 en XSD).

    Usa ``desglose_por_tipo`` persistido (JSON/JSONB: lista de dicts; importes como str o número).
    Solo si falta o no aplica, una fila sintética desde totales (legacy / sin snapshot).
    """
    raw: Any = factura.get("desglose_por_tipo")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    elif isinstance(raw, dict):
        raw = [raw]
    if isinstance(raw, list) and len(raw) > 0:
        fe = factura.get("motivo_exencion")
        ft = factura.get("tipo_no_sujecion")
        out: list[dict[str, Any]] = []
        for x in raw[:12]:
            d = dict(x) if isinstance(x, dict) else {}
            if fe and not str(d.get("motivo_exencion") or "").strip():
                d["motivo_exencion"] = fe
            if ft and not str(d.get("tipo_no_sujecion") or "").strip():
                d["tipo_no_sujecion"] = ft
            out.append(d)
        return out

    base = factura.get("base_imponible")
    cuota = factura.get("cuota_iva")
    tipo_explicit = factura.get("tipo_iva_porcentaje")
    if tipo_explicit is None:
        tipo_explicit = factura.get("iva_porcentaje")
    b_d = _to_decimal_money(base)
    c_d = _to_decimal_money(cuota)
    tipo_d: Decimal | None
    if tipo_explicit is not None and str(tipo_explicit).strip() != "":
        tipo_d = quantize_financial(tipo_explicit)
    else:
        inferred = _infer_tipo_impositivo_pct(b_d, c_d)
        tipo_d = inferred if inferred is not None else Decimal("0.00")

    return [
        {
            "tipo_iva_porcentaje": tipo_d,
            "base_imponible": base,
            "cuota_iva": cuota,
            "cuota_recargo_equivalencia": factura.get("cuota_recargo_equivalencia"),
            "cuota_retencion_irpf": factura.get("cuota_retencion_irpf"),
            "motivo_exencion": factura.get("motivo_exencion"),
            "tipo_no_sujecion": factura.get("tipo_no_sujecion"),
        }
    ]


def _iva_catalog_key(tipo_pct: Decimal) -> str:
    return str(quantize_financial(tipo_pct))


def _append_detalle_desglose(desglose_el: etree._Element, row: Mapping[str, Any]) -> None:
    det = etree.SubElement(desglose_el, q(NS_SF, "DetalleDesglose"))
    base_d = _to_decimal_money(row.get("base_imponible"))
    cuota_d = _to_decimal_money(row.get("cuota_iva"))
    re_cuota_d = _to_decimal_money(row.get("cuota_recargo_equivalencia"))

    raw_tipo = row.get("tipo_iva_porcentaje")
    tipo_pct_d: Decimal | None
    if raw_tipo is not None and str(raw_tipo).strip() != "":
        tipo_pct_d = quantize_financial(raw_tipo)
    else:
        inferred = _infer_tipo_impositivo_pct(base_d, cuota_d)
        tipo_pct_d = inferred if inferred is not None else Decimal("0.00")

    motivo = str(row.get("motivo_exencion") or "").strip().upper()
    tipo_ns = str(row.get("tipo_no_sujecion") or "").strip().upper()

    _txt(det, q(NS_SF, "Impuesto"), "01")
    _txt(det, q(NS_SF, "ClaveRegimen"), "01")

    if motivo in _EXENTAS_AEAT:
        _txt(det, q(NS_SF, "OperacionExenta"), motivo)
    elif tipo_ns in ("N1", "N2"):
        _txt(det, q(NS_SF, "CalificacionOperacion"), tipo_ns)
    else:
        _txt(det, q(NS_SF, "CalificacionOperacion"), "S1")
        _txt(det, q(NS_SF, "TipoImpositivo"), fiscal_amount_string_two_decimals(tipo_pct_d))

    _txt(det, q(NS_SF, "BaseImponibleOimporteNoSujeto"), fiscal_amount_string_two_decimals(base_d))
    _txt(det, q(NS_SF, "CuotaRepercutida"), fiscal_amount_string_two_decimals(cuota_d))

    if re_cuota_d > Decimal("0"):
        rk = _iva_catalog_key(tipo_pct_d)
        tre_stat = RECARGO_EQUIVALENCIA_POR_IVA_PCT.get(rk, Decimal("0.00"))
        if tre_stat > Decimal("0"):
            _txt(det, q(NS_SF, "TipoRecargoEquivalencia"), fiscal_amount_string_two_decimals(tre_stat))
            _txt(det, q(NS_SF, "CuotaRecargoEquivalencia"), fiscal_amount_string_two_decimals(re_cuota_d))
    # Nota: el XSD VeriFactu no define nodo de retención IRPF; el importe total debe reflejar
    # base + IVA + RE − IRPF vía ``ImporteTotal`` (Math Engine).


@dataclass(frozen=True, slots=True)
class RegistroAnteriorAEAT:
    """Datos de ``Encadenamiento/RegistroAnterior`` (factura inmediatamente anterior)."""

    id_emisor_factura: str
    num_serie_factura: str
    fecha_expedicion: str  # DD-MM-YYYY
    huella: str


@dataclass(frozen=True, slots=True)
class FacturaRectificadaRefAEAT:
    id_emisor_factura: str
    num_serie_factura: str
    fecha_expedicion: str  # DD-MM-YYYY


def build_cabecera_obligado_emision(
    *,
    nombre_razon: str,
    nif: str,
) -> etree._Element:
    """``Cabecera`` con ``ObligadoEmision`` (equivalente lógico a ID emisor + nombre)."""
    cab = etree.Element(q(NS_LR, "Cabecera"))
    oblig = etree.SubElement(cab, q(NS_SF, "ObligadoEmision"))
    _txt(oblig, q(NS_SF, "NombreRazon"), nombre_razon or nif)
    _txt(oblig, q(NS_SF, "NIF"), str(nif).strip())
    return cab


def _append_rectificada_placeholder_if_needed(
    reg: etree._Element,
    tipo: str,
    f_rect: FacturaRectificadaRefAEAT | None,
) -> None:
    if not str(tipo).strip().upper().startswith("R") or f_rect is None:
        return
    fr = etree.SubElement(reg, q(NS_SF, "FacturasRectificadas"))
    rid = etree.SubElement(fr, q(NS_SF, "IDFacturaRectificada"))
    _txt(rid, q(NS_SF, "IDEmisorFactura"), f_rect.id_emisor_factura)
    _txt(rid, q(NS_SF, "NumSerieFactura"), f_rect.num_serie_factura)
    _txt(rid, q(NS_SF, "FechaExpedicionFactura"), f_rect.fecha_expedicion)


def build_registro_alta_unsigned(
    *,
    factura: Mapping[str, Any],
    empresa: Mapping[str, Any],
    cliente: Mapping[str, Any],
    fingerprint: str,
    registro_anterior: RegistroAnteriorAEAT | None,
    rectificada: FacturaRectificadaRefAEAT | None,
    fecha_hora_gen: datetime | None = None,
) -> etree._Element:
    """
    Nodo ``RegistroAlta`` (sin ``ds:Signature``) listo para firma XAdES enveloped.
    """
    num = str(
        factura.get("num_factura") or factura.get("numero_factura") or ""
    ).strip()
    fecha_emision_raw = str(factura.get("fecha_emision") or "").strip()
    fecha_dd_mm_yyyy = fecha_iso_u_otra_a_dd_mm_yyyy(fecha_emision_raw)

    total = _to_decimal_money(factura.get("total_factura"))

    tipo = str(factura.get("tipo_factura") or "F1").strip().upper() or "F1"
    nif_emisor = str(factura.get("nif_emisor") or empresa.get("nif") or "").strip()
    nif_dest = str(cliente.get("nif") or "").strip()
    nombre_emisor = str(
        empresa.get("nombre_comercial") or empresa.get("nombre_legal") or ""
    ).strip()
    nombre_dest = str(cliente.get("nombre") or "").strip()

    ts_gen = fecha_hora_gen or datetime.now(timezone.utc)
    if ts_gen.tzinfo is None:
        ts_gen = ts_gen.replace(tzinfo=timezone.utc)
    fecha_hora_iso = ts_gen.astimezone(timezone.utc).isoformat()

    reg = etree.Element(q(NS_SF, "RegistroAlta"))

    _txt(reg, q(NS_SF, "IDVersion"), "1.0")

    idf = etree.SubElement(reg, q(NS_SF, "IDFactura"))
    _txt(idf, q(NS_SF, "IDEmisorFactura"), nif_emisor)
    _txt(idf, q(NS_SF, "NumSerieFactura"), num or "SIN-NUM")
    _txt(idf, q(NS_SF, "FechaExpedicionFactura"), fecha_dd_mm_yyyy)

    _txt(reg, q(NS_SF, "NombreRazonEmisor"), nombre_emisor or nif_emisor)
    _txt(reg, q(NS_SF, "RechazoPrevio"), "N")
    _txt(reg, q(NS_SF, "TipoFactura"), tipo)

    if str(tipo).strip().upper() in {"R1", "R2", "R3", "R4", "R5"}:
        _txt(reg, q(NS_SF, "TipoRectificativa"), "I")

    _append_rectificada_placeholder_if_needed(reg, tipo, rectificada)

    desc_op = (str(factura.get("descripcion_operacion") or "").strip()) or (
        f"Operación sujeta a IVA — factura {num}"
    )[:500]
    _txt(reg, q(NS_SF, "DescripcionOperacion"), desc_op)

    _txt(reg, q(NS_SF, "FacturaSimplificadaArt7273"), "N")
    _txt(reg, q(NS_SF, "FacturaSinIdentifDestinatarioArt61d"), "N")
    _txt(reg, q(NS_SF, "Macrodato"), "N")

    if nif_dest and len(nif_dest.strip()) == 9:
        dests = etree.SubElement(reg, q(NS_SF, "Destinatarios"))
        idd = etree.SubElement(dests, q(NS_SF, "IDDestinatario"))
        _txt(idd, q(NS_SF, "NombreRazon"), nombre_dest or nif_dest)
        _txt(idd, q(NS_SF, "NIF"), nif_dest.strip())

    rows = _factura_desglose_rows(factura)
    desg = etree.SubElement(reg, q(NS_SF, "Desglose"))
    cuota_total_acc = Decimal("0.00")
    for r in rows:
        _append_detalle_desglose(desg, r)
        cuota_total_acc += _to_decimal_money(r.get("cuota_iva"))
    cuota_total_acc = quantize_financial(cuota_total_acc)

    _txt(reg, q(NS_SF, "CuotaTotal"), fiscal_amount_string_two_decimals(cuota_total_acc))
    _txt(reg, q(NS_SF, "ImporteTotal"), fiscal_amount_string_two_decimals(total))

    enc = etree.SubElement(reg, q(NS_SF, "Encadenamiento"))
    if registro_anterior is not None:
        ra = etree.SubElement(enc, q(NS_SF, "RegistroAnterior"))
        _txt(ra, q(NS_SF, "IDEmisorFactura"), registro_anterior.id_emisor_factura)
        _txt(ra, q(NS_SF, "NumSerieFactura"), registro_anterior.num_serie_factura)
        _txt(ra, q(NS_SF, "FechaExpedicionFactura"), registro_anterior.fecha_expedicion)
        _txt(ra, q(NS_SF, "Huella"), registro_anterior.huella.strip())
    else:
        _txt(enc, q(NS_SF, "PrimerRegistro"), "S")

    sif = etree.SubElement(reg, q(NS_SF, "SistemaInformatico"))
    _txt(sif, q(NS_SF, "NombreRazon"), nombre_emisor or nif_emisor)
    _txt(sif, q(NS_SF, "NIF"), nif_emisor)
    _txt(sif, q(NS_SF, "NombreSistemaInformatico"), "ABLogisticsOS")
    _txt(sif, q(NS_SF, "IdSistemaInformatico"), "01")
    _txt(sif, q(NS_SF, "Version"), "1.0")
    _txt(sif, q(NS_SF, "NumeroInstalacion"), "1")
    _txt(sif, q(NS_SF, "TipoUsoPosibleSoloVerifactu"), "S")
    _txt(sif, q(NS_SF, "TipoUsoPosibleMultiOT"), "N")
    _txt(sif, q(NS_SF, "IndicadorMultiplesOT"), "N")

    _txt(reg, q(NS_SF, "FechaHoraHusoGenRegistro"), fecha_hora_iso)
    _txt(reg, q(NS_SF, "TipoHuella"), "01")
    _txt(reg, q(NS_SF, "Huella"), str(fingerprint).strip())

    return reg


def inner_xml_fragment_unsigned_alta_for_tests(
    *,
    factura: Mapping[str, Any],
    empresa: Mapping[str, Any],
    cliente: Mapping[str, Any],
    fingerprint: str,
    registro_anterior: RegistroAnteriorAEAT | None,
    rectificada: FacturaRectificadaRefAEAT | None = None,
) -> str:
    """Cabecera + RegistroFactura + RegistroAlta (sin firma), UTF-8 sin declaración XML."""
    nombre_oblig = str(
        empresa.get("nombre_comercial") or empresa.get("nombre_legal") or ""
    ).strip()
    nif_oblig = str(empresa.get("nif") or factura.get("nif_emisor") or "").strip()
    cab = build_cabecera_obligado_emision(
        nombre_razon=nombre_oblig or nif_oblig, nif=nif_oblig
    )
    alta = build_registro_alta_unsigned(
        factura=factura,
        empresa=empresa,
        cliente=cliente,
        fingerprint=fingerprint,
        registro_anterior=registro_anterior,
        rectificada=rectificada,
    )
    rf = etree.Element(q(NS_LR, "RegistroFactura"))
    rf.append(alta)
    parts = [
        etree.tostring(cab, encoding="utf-8", xml_declaration=False),
        etree.tostring(rf, encoding="utf-8", xml_declaration=False),
    ]
    return b"".join(parts).decode("utf-8")


def inner_xml_fragment_from_signed_registro_alta(
    *,
    empresa: Mapping[str, Any],
    factura: Mapping[str, Any],
    signed_registro_alta_xml: bytes,
) -> str:
    """
    Tras ``sign_xml_xades`` sobre el nodo ``RegistroAlta``, envuelve en ``RegistroFactura``
    y antepone ``Cabecera`` (misma fuente que el alta firmada).
    """
    parser = etree.XMLParser(resolve_entities=False)
    root = etree.fromstring(signed_registro_alta_xml, parser=parser)
    if root.tag != q(NS_SF, "RegistroAlta"):
        raise ValueError(
            "Se esperaba RegistroAlta como raíz del XML firmado para VeriFactu (AEAT)."
        )
    nombre_oblig = str(
        empresa.get("nombre_comercial") or empresa.get("nombre_legal") or ""
    ).strip()
    nif_oblig = str(empresa.get("nif") or factura.get("nif_emisor") or "").strip()
    cab = build_cabecera_obligado_emision(
        nombre_razon=nombre_oblig or nif_oblig, nif=nif_oblig
    )
    rf = etree.Element(q(NS_LR, "RegistroFactura"))
    rf.append(root)
    parts = [
        etree.tostring(cab, encoding="utf-8", xml_declaration=False),
        etree.tostring(rf, encoding="utf-8", xml_declaration=False),
    ]
    return b"".join(parts).decode("utf-8")
