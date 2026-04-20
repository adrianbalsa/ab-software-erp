from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import qrcode
from fpdf import FPDF

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE
from app.core.i18n import get_translator
from app.schemas.esg import HuellaCarbonoMensualOut
from app.services.pdf_fonts import register_brand_fonts

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

ZINC_800 = (39, 39, 42)
ZINC_500 = (113, 113, 122)
ZINC_200 = (228, 228, 231)
EMERALD_600 = (5, 150, 105)
EMERALD_100 = (209, 250, 229)


def _pdf_output_bytes(pdf: FPDF) -> bytes:
    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1")


def _fmt_num(n: float, dec: int = 2) -> str:
    fmt = f"{{:,.{dec}f}}"
    return fmt.format(n).replace(",", "X").replace(".", ",").replace("X", ".")


def _sello_digital(empresa_id: str, anio: int, mes: int, total_co2: float) -> str:
    raw = f"AB-ESG|{empresa_id}|{anio:04d}-{mes:02d}|{total_co2:.8f}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def generar_certificado_huella_carbono_pdf(
    *,
    empresa_nombre: str,
    empresa_id: str,
    huella: HuellaCarbonoMensualOut,
    lang: str | None = None,
) -> bytes:
    """
    PDF «Certificado de Huella de Carbono» listo para licitaciones:
    totales, media/porte, ahorro estimado, comparativa por vehículo y sello digital AB Logistics OS.
    """
    t = get_translator(lang)
    sello = _sello_digital(empresa_id, huella.anio, huella.mes, huella.total_co2_kg)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    body, mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    logo = _BACKEND_ROOT / "assets" / "logo.png"
    if logo.is_file():
        pdf.image(str(logo), x=14, y=12, w=22)

    pdf.set_xy(14, 14)
    pdf.set_font(body, "B", 16)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 8, t("AB Logistics OS"), align="R", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, t("ESG certification · Operational footprint"), align="R", ln=1)

    pdf.ln(10)
    pdf.set_font(body, "B", 18)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 10, t("Carbon footprint certificate"), ln=1)
    pdf.set_font(body, "", 10)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(
        0,
        6,
        t("Period: {month}/{year} · Company: {name}").format(
            month=f"{huella.mes:02d}", year=huella.anio, name=empresa_nombre
        ),
        ln=1,
    )
    pdf.ln(6)

    pdf.set_fill_color(*EMERALD_100)
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_line_width(0.3)
    box_y = pdf.get_y()
    pdf.rect(14, box_y, 182, 40, "DF")
    pdf.set_xy(18, box_y + 4)
    pdf.set_font(body, "B", 11)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 6, t("Period summary"), ln=1)
    pdf.set_font(body, "", 10)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(18)
    pdf.cell(
        0,
        6,
        t("Total CO2 equivalent emitted: {v} kg").format(v=_fmt_num(huella.total_co2_kg, 3)),
        ln=1,
    )
    pdf.set_x(18)
    pdf.cell(
        0,
        6,
        t("Actual road km (routes): {v} km").format(v=_fmt_num(huella.total_km_reales, 2)),
        ln=1,
    )
    pdf.set_x(18)
    pdf.cell(
        0,
        6,
        t("Invoiced shipments: {n} · Avg CO2/shipment: {v} kg").format(
            n=huella.num_portes_facturados, v=_fmt_num(huella.media_co2_por_porte_kg, 3)
        ),
        ln=1,
    )
    pdf.set_x(18)
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(
        0,
        6,
        t("Estimated savings (optimised routes vs +15% km unoptimised): {v} kg CO2eq").format(
            v=_fmt_num(huella.ahorro_estimado_rutas_optimizadas_kg, 3)
        ),
        ln=1,
    )
    pdf.set_y(box_y + 44)

    # Gráfico de barras: vehículos (más vs menos emisiones en el mes)
    pdf.set_font(body, "B", 12)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 8, t("Comparison by vehicle (kg CO2 in the period)"), ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "Bars sorted from highest to lowest impact. Includes shipments without an assigned vehicle (global factor)."
        ),
    )
    pdf.ln(2)

    barras = [v for v in huella.por_vehiculo if v.co2_kg > 0]
    if not barras:
        pdf.set_font(body, "", 9)
        pdf.set_text_color(*ZINC_500)
        pdf.cell(0, 6, t("No per-vehicle breakdown in the period."), ln=1)
    else:
        max_co2 = max(b.co2_kg for b in barras)
        chart_w = 120.0
        bar_h = 5.5
        x0 = 18.0
        y_chart = pdf.get_y()
        for i, b in enumerate(barras[:14]):
            y = y_chart + i * (bar_h + 2)
            if y > 250:
                break
            label = (b.matricula + " — " + b.etiqueta)[:52]
            if len(b.matricula + " — " + b.etiqueta) > 52:
                label += "…"
            w_bar = (b.co2_kg / max_co2) * chart_w if max_co2 > 0 else 0
            pdf.set_xy(x0, y)
            pdf.set_font(body, "", 7)
            pdf.set_text_color(*ZINC_800)
            pdf.cell(62, bar_h, label, align="L")
            pdf.set_fill_color(82, 82, 91)
            pdf.rect(x0 + 64, y + 0.8, w_bar, bar_h - 1.6, "F")
            pdf.set_xy(x0 + 64 + chart_w + 2, y)
            pdf.set_font(mono, "", 7)
            pdf.cell(24, bar_h, _fmt_num(b.co2_kg, 2), align="R")
        pdf.set_y(y_chart + min(len(barras), 14) * (bar_h + 2) + 6)

    pdf.ln(6)
    # Sello digital
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_fill_color(236, 253, 245)
    pdf.set_line_width(0.4)
    sy = pdf.get_y()
    pdf.rect(14, sy, 182, 28, "DF")
    pdf.set_xy(18, sy + 3)
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 5, t("AB Logistics OS digital seal"), ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(18)
    pdf.multi_cell(
        166,
        4,
        t(
            "Document generated from the AB Logistics OS platform. Integrity verifiable via SHA-256 fingerprint of the period and declared totals.\nIdentifier: {fp}…"
        ).format(fp=sello[:32]),
    )
    pdf.set_font(mono, "", 6)
    pdf.set_text_color(*ZINC_500)
    pdf.set_xy(18, sy + 22)
    pdf.cell(166, 4, sello, ln=1)

    pdf.ln(36)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "Methodology: kg CO2eq ≈ real km (Distance Matrix / cache) × tonnes × kg/(t·km) factor for the vehicle or global factor. Savings compare against a scenario with +15% km from lack of route optimisation. Indicative values for tenders and reporting do not replace external audits."
        ),
    )

    return _pdf_output_bytes(pdf)


def generar_certificado_huella_carbono_pdf_from_dict(
    *,
    empresa_nombre: str,
    empresa_id: str,
    huella_dict: dict[str, Any],
    lang: str | None = None,
) -> bytes:
    """Compat tests / serialización JSON."""
    h = HuellaCarbonoMensualOut.model_validate(huella_dict)
    return generar_certificado_huella_carbono_pdf(
        empresa_nombre=empresa_nombre,
        empresa_id=empresa_id,
        huella=h,
        lang=lang,
    )


@dataclass(frozen=True)
class EsgPorteCertificatePdfModel:
    """Payload para PDF certificado operativo (GLEC / ISO 14083 alineado)."""

    certificate_id: str
    content_fingerprint_sha256: str
    empresa_nombre: str
    empresa_nif: str
    porte_id: str
    fecha: str
    origen: str
    destino: str
    km_estimados: float
    km_reales: float | None
    real_distance_km: float | None
    km_vacio: float | None
    engine_class: str | None
    fuel_type: str | None
    vehiculo_label: str
    normativa_euro: str
    glec_gco2_km_full: float
    glec_gco2_km_empty: float
    co2_total_kg: float
    euro_iii_baseline_kg: float
    ahorro_kg: float
    nox_total_kg: float
    subcontratado: bool
    scope_note: str
    verify_url: str | None = None


@dataclass(frozen=True)
class EsgFacturaCertificatePdfModel:
    certificate_id: str
    content_fingerprint_sha256: str
    empresa_nombre: str
    empresa_nif: str
    factura_id: int
    numero_factura: str
    fecha_emision: str
    cliente_nombre: str
    esg_portes_count: int
    esg_total_km: float
    esg_total_co2_kg: float
    esg_euro_iii_baseline_kg: float
    esg_ahorro_kg: float
    verify_url: str | None = None


def _pdf_section_title(pdf: FPDF, body: str, title: str) -> None:
    pdf.set_font(body, "B", 11)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 7, title, ln=1)
    pdf.ln(1)


def _pdf_kv(pdf: FPDF, body: str, k: str, v: str) -> None:
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.multi_cell(0, 5, f"{k}: {v}", align="L")


def generar_pdf_certificado_esg_porte_glec(
    model: EsgPorteCertificatePdfModel, *, lang: str | None = None
) -> bytes:
    """
    Certificado «bank-ready»: logo, NIF, metodología GLEC v2.0 / ISO 14083, desglose y pie de auditoría.
    """
    t = get_translator(lang)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    body, mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    logo = _BACKEND_ROOT / "assets" / "logo.png"
    if logo.is_file():
        pdf.image(str(logo), x=14, y=12, w=20)

    pdf.set_xy(14, 14)
    pdf.set_font(body, "B", 15)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 8, t("AB Logistics OS"), align="R", ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(
        0,
        4,
        t("GLEC / ISO 14083 logistics and carbon certificate (v2.0 framework)"),
        align="R",
        ln=1,
    )

    pdf.ln(16)
    pdf.set_font(body, "B", 16)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 9, t("ESG certificate — Transport / service"), ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(
        0,
        5,
        t("Issued UTC: {ts}Z").format(ts=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        ln=1,
    )
    pdf.ln(4)

    _pdf_section_title(pdf, body, t("Issuer"))
    _pdf_kv(pdf, body, t("Legal name"), model.empresa_nombre)
    _pdf_kv(pdf, body, t("Tax ID"), model.empresa_nif or "—")
    pdf.ln(2)

    _pdf_section_title(pdf, body, t("Service identification"))
    _pdf_kv(pdf, body, t("Shipment ID"), model.porte_id)
    _pdf_kv(pdf, body, t("Operational date"), model.fecha)
    _pdf_kv(pdf, body, t("Origin → Destination"), f"{model.origen} → {model.destino}")
    dist_real = (
        t("{v} km (route / telemetry)").format(v=_fmt_num(model.real_distance_km, 3))
        if model.real_distance_km is not None
        else "—"
    )
    dist_est = t("{v} km (record / operational estimate)").format(v=_fmt_num(model.km_estimados, 3))
    dist_kmr = (
        t("{v} km").format(v=_fmt_num(model.km_reales, 3)) if model.km_reales is not None else "—"
    )
    _pdf_kv(pdf, body, t("Real distance (km)"), dist_real)
    _pdf_kv(pdf, body, t("Recorded km (operational estimate)"), dist_est)
    _pdf_kv(pdf, body, t("Actual km (portes table)"), dist_kmr)
    kv = f"{_fmt_num(model.km_vacio or 0.0, 2)} km" if model.km_vacio is not None else "—"
    _pdf_kv(pdf, body, t("Declared empty km"), kv)
    _pdf_kv(
        pdf,
        body,
        t("Subcontracted"),
        t("Yes (Scope 3)") if model.subcontratado else t("No (Scope 1)"),
    )
    pdf.ln(2)

    _pdf_section_title(pdf, body, t("Vehicle and factors (GLEC)"))
    _pdf_kv(pdf, body, t("Vehicle"), model.vehiculo_label)
    _pdf_kv(pdf, body, t("EURO standard (reporting)"), model.normativa_euro)
    _pdf_kv(pdf, body, t("Engine class (GLEC)"), model.engine_class or "—")
    _pdf_kv(pdf, body, t("Fuel (GLEC)"), model.fuel_type or "—")
    _pdf_kv(
        pdf,
        body,
        t("g CO₂/km factor (loaded / empty)"),
        f"{_fmt_num(model.glec_gco2_km_full, 1)} / {_fmt_num(model.glec_gco2_km_empty, 1)}",
    )
    pdf.ln(2)

    _pdf_section_title(pdf, body, t("Results"))
    _pdf_kv(pdf, body, t("Total CO2 (GLEC)"), f"{_fmt_num(model.co2_total_kg, 6)} kg CO₂eq")
    _pdf_kv(pdf, body, t("Euro III baseline"), f"{_fmt_num(model.euro_iii_baseline_kg, 6)} kg CO₂eq")
    _pdf_kv(pdf, body, t("Savings vs Euro III"), f"{_fmt_num(model.ahorro_kg, 6)} kg CO₂eq")
    _pdf_kv(pdf, body, t("Total NOx (EURO standard)"), f"{_fmt_num(model.nox_total_kg, 6)} kg")
    pdf.ln(2)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "Methodology: calculated per GLEC Framework v2.0 (simplified engine implementation) and ISO 14083 transport intensity reference. g CO₂/km factors per loaded/empty leg come from the internal GLEC table aligned with calculate_co2_footprint. NOx: total km × g/km per declared EURO standard."
        ),
    )
    pdf.ln(4)

    # Pie auditoría
    sy = pdf.get_y()
    pdf.set_fill_color(236, 253, 245)
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_line_width(0.3)
    pdf.rect(14, sy, 182, 36, "DF")
    pdf.set_xy(18, sy + 3)
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 5, t("Document audit and integrity"), ln=1)
    pdf.set_font(mono, "", 7)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(18)
    pdf.multi_cell(170, 4, t("Certificate ID: {id}").format(id=model.certificate_id))
    pdf.set_x(18)
    pdf.multi_cell(
        170, 4, t("Content fingerprint (SHA-256): {fp}").format(fp=model.content_fingerprint_sha256)
    )
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*ZINC_500)
    pdf.set_x(18)
    pdf.multi_cell(
        170,
        4,
        t("The esg_certificate_documents table stores the PDF file SHA-256 and this content fingerprint.")
        + " "
        + str(model.scope_note),
    )

    return _pdf_output_bytes(pdf)


def generar_pdf_certificado_esg_factura_glec(
    model: EsgFacturaCertificatePdfModel, *, lang: str | None = None
) -> bytes:
    t = get_translator(lang)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    body, mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    logo = _BACKEND_ROOT / "assets" / "logo.png"
    if logo.is_file():
        pdf.image(str(logo), x=14, y=12, w=20)

    pdf.set_xy(14, 14)
    pdf.set_font(body, "B", 15)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 8, t("AB Logistics OS"), align="R", ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(
        0,
        4,
        t("Aggregated ESG certificate — GLEC v2.0 / ISO 14083"),
        align="R",
        ln=1,
    )

    pdf.ln(16)
    pdf.set_font(body, "B", 16)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 9, t("ESG certificate — Invoice (aggregated shipments)"), ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(
        0,
        5,
        t("Issued UTC: {ts}Z").format(ts=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        ln=1,
    )
    pdf.ln(4)

    _pdf_section_title(pdf, body, t("Issuer"))
    _pdf_kv(pdf, body, t("Legal name"), model.empresa_nombre)
    _pdf_kv(pdf, body, t("Tax ID"), model.empresa_nif or "—")
    pdf.ln(2)

    _pdf_section_title(pdf, body, t("Document"))
    _pdf_kv(pdf, body, t("Invoice ID"), str(model.factura_id))
    _pdf_kv(pdf, body, t("Number"), model.numero_factura)
    _pdf_kv(pdf, body, t("Issue date"), model.fecha_emision)
    _pdf_kv(pdf, body, t("Customer"), model.cliente_nombre)
    pdf.ln(2)

    _pdf_section_title(pdf, body, t("Aggregated footprint (sum per invoiced shipment)"))
    _pdf_kv(pdf, body, t("Shipments included"), str(model.esg_portes_count))
    _pdf_kv(pdf, body, t("Operational km summed"), f"{_fmt_num(model.esg_total_km, 3)} km")
    _pdf_kv(pdf, body, t("Total CO2 (GLEC)"), f"{_fmt_num(model.esg_total_co2_kg, 6)} kg CO₂eq")
    _pdf_kv(pdf, body, t("Euro III baseline"), f"{_fmt_num(model.esg_euro_iii_baseline_kg, 6)} kg CO₂eq")
    _pdf_kv(pdf, body, t("Savings vs Euro III"), f"{_fmt_num(model.esg_ahorro_kg, 6)} kg CO₂eq")
    pdf.ln(4)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "Methodology: sum of GLEC models for each shipment linked to the invoice (esg_certificate_co2_vs_euro_iii), with the same distance and fuel structure per shipment. Calculated per GLEC Framework v2.0 / ISO 14083 (operational reference)."
        ),
    )
    pdf.ln(3)
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 6, t("Calculation methodology (ISO 14083)"), ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "ISO 14083:2021 — diesel reference factor {fac} kg CO₂eq / L (explicit, no "
            "substitution). GLEC v2.0 per-shipment intensities sum to the totals above for "
            "third-party reconciliation."
        ).format(fac=ISO_14083_DIESEL_CO2_KG_PER_LITRE),
    )
    pdf.ln(4)

    sy = pdf.get_y()
    pdf.set_fill_color(236, 253, 245)
    pdf.set_draw_color(*EMERALD_600)
    pdf.rect(14, sy, 182, 28, "DF")
    pdf.set_xy(18, sy + 3)
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 5, t("Document audit and integrity"), ln=1)
    pdf.set_font(mono, "", 7)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(18)
    pdf.multi_cell(170, 4, t("Certificate ID: {id}").format(id=model.certificate_id))
    pdf.set_x(18)
    pdf.multi_cell(
        170, 4, t("Content fingerprint (SHA-256): {fp}").format(fp=model.content_fingerprint_sha256)
    )
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*ZINC_500)
    pdf.set_x(18)
    pdf.multi_cell(
        170,
        4,
        t("esg_certificate_documents: PDF SHA-256 and content fingerprint."),
    )

    if model.verify_url:
        qr_buf = io.BytesIO()
        qrcode.make(model.verify_url, border=1).save(qr_buf, format="PNG")
        qr_buf.seek(0)
        qr_w = 22.0
        x_qr = float(pdf.w) - 14.0 - qr_w
        y_qr = float(pdf.h) - 14.0 - qr_w
        pdf.image(qr_buf, x=x_qr, y=y_qr, w=qr_w, type="PNG")

    return _pdf_output_bytes(pdf)
