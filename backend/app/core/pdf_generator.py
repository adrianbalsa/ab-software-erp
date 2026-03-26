from __future__ import annotations

from datetime import datetime, timezone
import base64
import io
from typing import Any

from fpdf import FPDF


def generate_esg_certificate(report_data: dict[str, Any]) -> bytes:
    """
    Genera certificado mensual ESG en PDF (bytes).
    """
    empresa = str(report_data.get("empresa_nombre") or "AB Logistics OS").strip()
    periodo = str(report_data.get("periodo") or "-").strip()
    total_co2 = float(report_data.get("total_co2_kg") or 0.0)
    total_portes = int(report_data.get("total_portes") or 0)
    total_km = float(report_data.get("total_km") or 0.0)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cabecera
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 9, "AB Logistics OS", ln=1)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(75, 85, 99)
    pdf.cell(0, 6, f"Empresa transportista: {empresa}", ln=1)
    pdf.ln(5)

    # Titulo
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(0, 9, "Certificado de Sostenibilidad y Huella de Carbono")
    pdf.ln(4)

    # Bloque central
    pdf.set_fill_color(239, 246, 255)
    pdf.set_draw_color(147, 197, 253)
    pdf.rect(10, pdf.get_y(), 190, 28, "DF")
    y = pdf.get_y() + 4
    pdf.set_xy(14, y)
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(30, 64, 175)
    pdf.cell(0, 6, f"Periodo certificado: {periodo}", ln=1)
    pdf.set_x(14)
    pdf.set_font("helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, f"{total_co2:,.2f} kg CO2", ln=1)
    pdf.ln(10)

    # Tabla resumen
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 8, "Resumen mensual de actividad", ln=1)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(243, 244, 246)
    pdf.cell(95, 8, "Indicador", border=1, fill=True)
    pdf.cell(95, 8, "Valor", border=1, fill=True, ln=1)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(95, 8, "Numero de portes", border=1)
    pdf.cell(95, 8, f"{total_portes}", border=1, ln=1)
    pdf.cell(95, 8, "Kilometros totales", border=1)
    pdf.cell(95, 8, f"{total_km:,.2f} km", border=1, ln=1)
    pdf.ln(6)

    # Pie
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(75, 85, 99)
    pdf.multi_cell(
        0,
        4.5,
        "Calculo basado en normativa Euro VI y estandares europeos de transporte B2B.",
    )
    pdf.cell(
        0,
        4.5,
        f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )

    return bytes(pdf.output(dest="S"))


def generate_invoice_verifactu_pdf(invoice_data: dict[str, Any], qr_png: bytes | None = None) -> bytes:
    """
    Plantilla simple de factura VeriFactu con QR de cotejo AEAT.
    """
    num = str(invoice_data.get("numero_factura") or invoice_data.get("num_factura") or "-").strip()
    fecha = str(invoice_data.get("fecha_emision") or "").strip()
    emisor = str(invoice_data.get("emisor_nombre") or invoice_data.get("nif_emisor") or "").strip()
    receptor = str(invoice_data.get("receptor_nombre") or invoice_data.get("nif_receptor") or "").strip()
    total = float(invoice_data.get("total_factura") or 0.0)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 9, f"Factura {num}", ln=1)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"Fecha: {fecha}", ln=1)
    pdf.cell(0, 6, f"Emisor: {emisor}", ln=1)
    pdf.cell(0, 6, f"Receptor: {receptor}", ln=1)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 9, f"Total: {total:,.2f} EUR", ln=1)

    if qr_png:
        try:
            pdf.image(io.BytesIO(qr_png), x=pdf.w - 58, y=20, w=38, h=38)
        except Exception:
            # Fallback: base64 inline not mandatory for render.
            _ = base64.b64encode(qr_png).decode("ascii")

    pdf.set_y(-26)
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(75, 85, 99)
    pdf.multi_cell(
        0,
        4.5,
        "Factura verificable en la sede electronica de la AEAT",
    )
    return bytes(pdf.output(dest="S"))
