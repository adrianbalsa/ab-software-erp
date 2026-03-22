from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fpdf import FPDF

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
) -> bytes:
    """
    PDF «Certificado de Huella de Carbono» listo para licitaciones:
    totales, media/porte, ahorro estimado, comparativa por vehículo y sello digital AB Logistics OS.
    """
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
    pdf.cell(0, 8, "AB Logistics OS", align="R", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, "Certificación ESG · Huella operativa", align="R", ln=1)

    pdf.ln(10)
    pdf.set_font(body, "B", 18)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 10, "Certificado de Huella de Carbono", ln=1)
    pdf.set_font(body, "", 10)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(
        0,
        6,
        f"Periodo: {huella.mes:02d}/{huella.anio} · Empresa: {empresa_nombre}",
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
    pdf.cell(0, 6, "Resumen del periodo", ln=1)
    pdf.set_font(body, "", 10)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(18)
    pdf.cell(
        0,
        6,
        f"Total CO₂ equivalente emitido: {_fmt_num(huella.total_co2_kg, 3)} kg",
        ln=1,
    )
    pdf.set_x(18)
    pdf.cell(
        0,
        6,
        f"Km reales acumulados (rutas carretera): {_fmt_num(huella.total_km_reales, 2)} km",
        ln=1,
    )
    pdf.set_x(18)
    pdf.cell(
        0,
        6,
        f"Portes facturados: {huella.num_portes_facturados} · Media CO₂/porte: {_fmt_num(huella.media_co2_por_porte_kg, 3)} kg",
        ln=1,
    )
    pdf.set_x(18)
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(
        0,
        6,
        f"Ahorro estimado (rutas optimizadas vs +15% km sin optimizar): {_fmt_num(huella.ahorro_estimado_rutas_optimizadas_kg, 3)} kg CO₂eq",
        ln=1,
    )
    pdf.set_y(box_y + 44)

    # Gráfico de barras: vehículos (más vs menos emisiones en el mes)
    pdf.set_font(body, "B", 12)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 8, "Comparativa por vehículo (kg CO₂ en el periodo)", ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        "Barras ordenadas de mayor a menor impacto. Incluye portes sin vehículo asignado (factor global).",
    )
    pdf.ln(2)

    barras = [v for v in huella.por_vehiculo if v.co2_kg > 0]
    if not barras:
        pdf.set_font(body, "", 9)
        pdf.set_text_color(*ZINC_500)
        pdf.cell(0, 6, "Sin desglose por vehículo en el periodo.", ln=1)
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
    pdf.cell(0, 5, "Sello digital AB Logistics OS", ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(18)
    pdf.multi_cell(
        166,
        4,
        "Documento generado desde la plataforma AB Logistics OS. Integridad verificable mediante "
        f"huella SHA-256 del periodo y totales declarados.\nIdentificador: {sello[:32]}…",
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
        "Metodología: kg CO₂eq ≈ km reales (Distance Matrix / caché) × toneladas × factor kg/(t·km) "
        "del vehículo o factor global. El ahorro compara frente a un escenario con +15% km por "
        "falta de optimización de ruta. Valores orientativos para licitaciones y reporting no "
        "sustituyen auditorías externas.",
    )

    return _pdf_output_bytes(pdf)


def generar_certificado_huella_carbono_pdf_from_dict(
    *,
    empresa_nombre: str,
    empresa_id: str,
    huella_dict: dict[str, Any],
) -> bytes:
    """Compat tests / serialización JSON."""
    h = HuellaCarbonoMensualOut.model_validate(huella_dict)
    return generar_certificado_huella_carbono_pdf(
        empresa_nombre=empresa_nombre,
        empresa_id=empresa_id,
        huella=h,
    )
