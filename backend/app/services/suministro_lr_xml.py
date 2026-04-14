"""
Construcción de XML **SuministroLR** (``RegFactuSistemaFacturacion``): ``Cabecera`` +
``RegistroFactura`` → ``RegistroAlta`` según XSD oficiales AEAT (tike/cont/ws).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from lxml import etree


NS_LR = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroLR.xsd"
)
NS_SF = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroInformacion.xsd"
)


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


def importe_12_2(value: float) -> str:
    return f"{float(value):.2f}"


def tipo_impositivo_str(base: float, cuota: float) -> str:
    if base and abs(base) > 1e-9:
        try:
            return f"{round((cuota / base) * 100.0, 2):.2f}".rstrip("0").rstrip(".") or "0"
        except (ZeroDivisionError, TypeError, ValueError):
            pass
    return "0"


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

    desg = etree.SubElement(reg, q(NS_SF, "Desglose"))
    det = etree.SubElement(desg, q(NS_SF, "DetalleDesglose"))
    _txt(det, q(NS_SF, "Impuesto"), "01")
    _txt(det, q(NS_SF, "ClaveRegimen"), "01")
    _txt(det, q(NS_SF, "CalificacionOperacion"), "S1")
    ti = tipo_impositivo_str(base, cuota)
    if ti and ti != "0":
        _txt(det, q(NS_SF, "TipoImpositivo"), ti)
    _txt(det, q(NS_SF, "BaseImponibleOimporteNoSujeto"), importe_12_2(base))
    _txt(det, q(NS_SF, "CuotaRepercutida"), importe_12_2(cuota))

    _txt(reg, q(NS_SF, "CuotaTotal"), importe_12_2(cuota))
    _txt(reg, q(NS_SF, "ImporteTotal"), importe_12_2(total))

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
