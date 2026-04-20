from __future__ import annotations

import datetime
from typing import Any

from fpdf import FPDF

from app.services.pdf_fonts import register_brand_fonts
from app.core.i18n import get_translator
from app.services.pdf_service import ZINC_200, ZINC_500, ZINC_800, EMERALD_600, draw_eco_footer_icon


def _pdf_out(pdf: FPDF) -> bytes:
    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1")


def generar_pdf_oficial(datos: dict[str, Any], *, lang: str | None = None) -> bytes:
    """
    Certificado ESG oficial — estilo diploma de sostenibilidad (grid limpio, Zinc / Emerald, Roboto).
    """
    t = get_translator(lang)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=22)
    body, _mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    pdf.set_draw_color(*EMERALD_600)
    pdf.set_line_width(0.75)
    pdf.rect(12, 10, pdf.w - 24, pdf.h - 26, "D")
    pdf.set_draw_color(*ZINC_200)
    pdf.set_line_width(0.2)
    pdf.rect(14, 12, pdf.w - 28, pdf.h - 30, "D")

    pdf.set_y(16)
    pdf.set_font(body, "B", 12)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 8, t("Sustainability diploma"), align="C", ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, t("Technical environmental compliance certificate"), align="C", ln=1)
    pdf.ln(4)

    pdf.set_font(body, "B", 11)
    pdf.set_text_color(*ZINC_800)
    pdf.multi_cell(
        0,
        6,
        t(
            "I, [LEGAL REPRESENTATIVE], as administrator, certify that the data recorded matches the digitally audited records, in line with digitisation standards required for grants and subsidies."
        ),
        align="J",
    )
    pdf.ln(6)

    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 6, t("Audited indicators"), ln=1)
    pdf.set_draw_color(*ZINC_200)
    pdf.set_fill_color(250, 250, 250)
    pdf.set_font(body, "B", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(100, 8, t("Indicator"), 1, 0, "L", True)
    pdf.cell(45, 8, t("Value"), 1, 0, "C", True)
    pdf.cell(45, 8, t("Unit"), 1, 1, "C", True)

    pdf.set_font(body, "", 9)
    pdf.set_fill_color(255, 255, 255)
    pdf.cell(100, 9, t("Document digitisation"), 1, 0, "L")
    pdf.cell(45, 9, str(datos.get("n_tickets", "")), 1, 0, "C")
    pdf.cell(45, 9, t("Units"), 1, 1, "C")

    pdf.cell(100, 9, t("Raw material savings (paper)"), 1, 0, "L")
    pdf.cell(45, 9, f"{float(datos.get('papel_kg', 0)):.2f}", 1, 0, "C")
    pdf.cell(45, 9, "kg", 1, 1, "C")

    pdf.set_text_color(*EMERALD_600)
    pdf.set_font(body, "B", 9)
    pdf.cell(100, 9, t("Carbon footprint reduction (CO2)"), 1, 0, "L")
    pdf.cell(45, 9, f"{float(datos.get('co2_total', 0)):.2f}", 1, 0, "C")
    pdf.cell(45, 9, "kg CO2eq", 1, 1, "C")

    pdf.ln(10)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 8, t("Digital signature and seal (internal representation)"), ln=1)

    pdf.set_y(-22)
    draw_eco_footer_icon(pdf, pdf.w / 2 - 3, pdf.h - 17)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 4, t("Ecological commitment · AB Logistics OS"), align="C", ln=1)
    pdf.set_text_color(*ZINC_500)
    pdf.set_font(body, "", 7)
    pdf.cell(
        0,
        4,
        t("Doc. ID {id}-ESG · Administrative use").format(id=datetime.datetime.now().strftime("%Y%m%d")),
        align="C",
        ln=1,
    )

    return _pdf_out(pdf)
