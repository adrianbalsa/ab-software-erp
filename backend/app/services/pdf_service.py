from __future__ import annotations

import base64
import datetime
import io
from pathlib import Path
from typing import Any

from fpdf import FPDF

from app.services.pdf_fonts import register_brand_fonts

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

# ─── Paleta marca (Tailwind) ─────────────────────────────────────────────────
ZINC_800 = (39, 39, 42)  # #27272a
ZINC_500 = (113, 113, 122)
ZINC_200 = (228, 228, 231)
EMERALD_600 = (5, 150, 105)  # #059669
EMERALD_500 = (16, 185, 129)
WHITE = (255, 255, 255)


def _pdf_output_bytes(pdf: FPDF) -> bytes:
    raw = pdf.output(dest="S")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return raw.encode("latin-1")


def _fmt_eur(v: float | int | None) -> str:
    try:
        x = float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return "—"
    return f"{x:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def draw_eco_footer_icon(pdf: FPDF, cx: float, cy: float) -> None:
    """Pequeño motivo planeta + hoja (refuerzo ecológico)."""
    pdf.set_fill_color(*EMERALD_600)
    pdf.ellipse(cx - 2.5, cy - 1.5, 5, 5, "F")
    pdf.set_draw_color(*EMERALD_500)
    pdf.set_line_width(0.25)
    pdf.ellipse(cx - 3, cy - 2, 6, 6, "D")
    pdf.set_fill_color(16, 185, 129)
    pdf.polygon([(cx + 4, cy + 1), (cx + 6.5, cy + 1), (cx + 5.2, cy - 2.2)], style="F")


class InvoicePDF(FPDF):
    """Factura AB Logistics OS — grid, Zinc / Emerald, VeriFactu."""

    def __init__(self) -> None:
        super().__init__()
        self.body_family = "helvetica"
        self.mono_family = "courier"
        self.set_auto_page_break(auto=True, margin=18)

    def header(self) -> None:
        logo = _BACKEND_ROOT / "assets" / "logo.png"
        if logo.is_file():
            self.image(str(logo), x=12, y=10, w=32)

        self.set_xy(12, 12)
        self.set_font(self.body_family, "B", 18)
        self.set_text_color(*EMERALD_600)
        self.cell(0, 8, "AB Logistics OS", align="R")
        self.ln(6)
        self.set_font(self.body_family, "B", 14)
        self.set_text_color(*ZINC_800)
        self.cell(0, 7, "Factura", align="R")
        self.ln(12)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(self.body_family, "", 8)
        self.set_text_color(*ZINC_500)
        self.cell(0, 5, f"Página {self.page_no()}", align="C")


def generar_pdf_factura(
    datos_empresa: dict[str, Any],
    datos_cliente: dict[str, Any],
    conceptos: list[dict[str, Any]],
) -> bytes:
    """
    PDF de factura con rejilla moderna, sección VeriFactu y fuentes de marca (Roboto / Roboto Mono).

    ``datos_empresa`` puede incluir (opcional): ``numero_factura``, ``fecha_emision``, ``num_factura``,
    ``base_imponible``, ``cuota_iva``, ``total_factura``, ``iva_porcentaje``, ``hash``.
    """
    pdf = InvoicePDF()
    body, mono = register_brand_fonts(pdf)
    pdf.body_family = body
    pdf.mono_family = mono

    pdf.add_page()
    pdf.set_margin(12)
    pdf.set_text_color(*ZINC_800)

    num = str(datos_empresa.get("numero_factura") or datos_empresa.get("num_factura") or "—")
    fecha = str(datos_empresa.get("fecha_emision") or datetime.date.today().isoformat())
    num_vf = str(datos_empresa.get("num_factura") or num)

    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(95, 5, f"Documento n.º {num}", align="L")
    pdf.cell(95, 5, f"Fecha emisión: {fecha}", align="R")
    pdf.ln(8)
    pdf.set_text_color(*ZINC_800)

    # ── Grid: Emisor | Receptor ─────────────────────────────────────────────
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    half = (usable - 4) / 2
    y0 = pdf.get_y()
    pdf.set_draw_color(*ZINC_200)
    pdf.set_fill_color(250, 250, 250)

    em_lines = [
        str(datos_empresa.get("nombre") or ""),
        f"NIF/CIF: {str(datos_empresa.get('nif') or '').strip() or '—'}",
    ]
    re_lines = [
        str(datos_cliente.get("nombre") or ""),
        f"NIF/CIF: {str(datos_cliente.get('nif') or '').strip() or '—'}",
        f"Ref. cliente: {datos_cliente.get('id', '')}",
    ]

    pdf.set_xy(pdf.l_margin, y0)
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(half, 6, "Emisor", border="LTR", align="L", fill=True)
    pdf.set_xy(pdf.l_margin + half + 4, y0)
    pdf.cell(half, 6, "Receptor", border="LTR", align="L", fill=True)
    pdf.ln(6)

    y1 = pdf.get_y()
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.set_xy(pdf.l_margin, y1)
    pdf.multi_cell(half, 5, "\n".join(em_lines), border="LBR", align="L")
    h_left = pdf.get_y() - y1
    pdf.set_xy(pdf.l_margin + half + 4, y1)
    pdf.multi_cell(half, 5, "\n".join(re_lines), border="LBR", align="L")
    h_right = pdf.get_y() - y1
    pdf.set_y(y1 + max(h_left, h_right) + 6)

    # ── Líneas de detalle (tabla) ───────────────────────────────────────────
    pdf.set_font(body, "B", 9)
    pdf.set_fill_color(*EMERALD_600)
    pdf.set_text_color(*WHITE)
    pdf.set_draw_color(*ZINC_200)
    pdf.cell(118, 8, "Concepto / servicio", 1, 0, "L", True)
    pdf.cell(65, 8, "Importe (EUR)", 1, 1, "R", True)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.set_fill_color(255, 255, 255)
    subtotal = 0.0
    for item in conceptos:
        raw_name = str(item.get("nombre", ""))
        nombre = raw_name if len(raw_name) <= 100 else raw_name[:97] + "…"
        try:
            precio = float(item.get("precio", 0) or 0)
        except (TypeError, ValueError):
            precio = 0.0
        subtotal += precio
        pdf.cell(118, 8, nombre, 1, 0, "L")
        pdf.cell(65, 8, _fmt_eur(precio), 1, 1, "R")

    # Totales
    base = datos_empresa.get("base_imponible")
    cuota = datos_empresa.get("cuota_iva")
    total = datos_empresa.get("total_factura")
    iva_pct = datos_empresa.get("iva_porcentaje")

    if base is None:
        base = subtotal
    if total is None:
        total = float(base or 0) + float(cuota or 0)

    pdf.ln(2)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(118, 6, "", 0, 0)
    if iva_pct is not None:
        pdf.cell(65, 6, f"Base imponible: {_fmt_eur(base)}", 0, 1, "R")
        pdf.cell(118, 6, "", 0, 0)
        pdf.cell(65, 6, f"IVA ({iva_pct}%): {_fmt_eur(cuota)}", 0, 1, "R")
    else:
        pdf.cell(65, 6, f"Base: {_fmt_eur(base)}", 0, 1, "R")
        if cuota is not None:
            pdf.cell(118, 6, "", 0, 0)
            pdf.cell(65, 6, f"Cuota IVA: {_fmt_eur(cuota)}", 0, 1, "R")
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(118, 8, "", 0, 0)
    pdf.cell(65, 8, f"Total {_fmt_eur(total)}", 0, 1, "R")

    # ── Evidencia VeriFactu + QR AEAT ─────────────────────────────────────────
    pdf.ln(6)
    hash_val = str(
        datos_empresa.get("hash")
        or datos_empresa.get("hash_registro")
        or "PENDIENTE_VALIDACION_AEAT"
    )
    qr_b64 = str(datos_empresa.get("qr_verifactu_base64") or "").strip()
    qr_bytes: bytes | None = None
    if qr_b64:
        try:
            qr_bytes = base64.b64decode(qr_b64.encode("ascii"))
        except Exception:
            qr_bytes = None

    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    qr_w_mm = 34.0
    gap = 4.0
    text_col_w = usable_w - (qr_w_mm + gap) if qr_bytes else usable_w

    y_box = pdf.get_y()
    hash_lines = max(1, (len(hash_val) + 88) // 88)
    text_block_h = 8.0 + 8.0 + 5.0 + hash_lines * 3.6
    box_h = max(text_block_h, qr_w_mm + 6.0) if qr_bytes else text_block_h

    pdf.set_draw_color(*EMERALD_600)
    pdf.set_line_width(0.35)
    pdf.set_fill_color(236, 253, 245)
    pdf.rect(pdf.l_margin, y_box, usable_w, box_h, "DF")

    pdf.set_xy(pdf.l_margin + 3, y_box + 2)
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(text_col_w - 6, 5, "Evidencia VeriFactu", ln=1)
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(pdf.l_margin + 3)
    pdf.multi_cell(
        text_col_w - 6,
        4,
        f"Identificador registro: {num_vf}\nHuella SHA-256 (encadenamiento SIF):",
    )
    pdf.set_font(mono, "", 7)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(pdf.l_margin + 3)
    pdf.multi_cell(text_col_w - 6, 3.5, hash_val)

    if qr_bytes:
        x_qr = pdf.l_margin + text_col_w + gap
        y_qr = y_box + (box_h - qr_w_mm) / 2
        try:
            pdf.image(io.BytesIO(qr_bytes), x=x_qr, y=y_qr, w=qr_w_mm)
        except Exception:
            pdf.set_xy(x_qr, y_qr + 2)
            pdf.set_font(body, "", 7)
            pdf.set_text_color(*ZINC_500)
            pdf.multi_cell(qr_w_mm, 4, "QR VeriFactu\n(no disponible)", align="C")

    pdf.set_y(y_box + box_h + 2)

    return _pdf_output_bytes(pdf)


def generar_pdf_certificado_emisiones_esg(
    *,
    empresa_nombre: str,
    empresa_id: str,
    meses: list[dict[str, Any]],
    co2_combustible_total_kg: float,
    litros_estimados_total: float,
    kg_co2_por_litro: float,
    eur_por_litro_ref: float,
    factor_huella_tkm: float | None = None,
) -> bytes:
    """
    Certificado mensual Scope 1 (combustible) — estilo diploma de sostenibilidad.

    Muestra el modelo de huella transporte: km x t x factor = kg CO2eq (referencia metodológica)
    y el desglose de datos registrados (combustible).
    """
    import os as _os

    f_tkm = float(
        factor_huella_tkm
        if factor_huella_tkm is not None
        else (_os.getenv("ECO_FACTOR_HUELLA_PORTE_KG_CO2_TKM") or "0.062")
    )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=22)
    body, _mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    # Marco diploma
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_line_width(0.8)
    pdf.rect(12, 10, pdf.w - 24, pdf.h - 28, "D")
    pdf.set_line_width(0.2)
    pdf.set_draw_color(*ZINC_200)
    pdf.rect(14, 12, pdf.w - 28, pdf.h - 32, "D")

    pdf.set_y(18)
    pdf.set_font(body, "B", 11)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 8, "DIPLOMA DE SOSTENIBILIDAD", align="C", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, "Emisiones de CO2 - referencia metodológica y datos registrados", align="C", ln=1)
    pdf.ln(4)

    pdf.set_font(body, "B", 12)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 10, "Certificado de emisiones (Scope 1 | combustible)", align="C", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.multi_cell(0, 5, f"Empresa: {empresa_nombre}\nID auditoría: {empresa_id}")
    pdf.ln(3)

    # Fórmula hero (modelo transporte)
    pdf.set_fill_color(236, 253, 245)
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_text_color(*ZINC_800)
    pdf.set_font(body, "B", 9)
    pdf.cell(0, 7, "Modelo de huella de transporte (t km)", ln=1)
    pdf.set_font(body, "", 9)
    formula = (
        f"km x toneladas x factor = kg CO2eq  =>  factor de referencia = {f_tkm:.4f} kg CO2 / (t km)"
    )
    pdf.multi_cell(0, 5, formula)
    pdf.ln(2)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        "Esta expresión describe el modelo ESG de portes en la plataforma. "
        "Los totales inferiores se obtienen a partir de gastos clasificados como COMBUSTIBLE (diesel).",
    )
    pdf.ln(3)

    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 7, "Metodología combustible (Scope 1)", ln=1)
    pdf.set_font(body, "", 8)
    pdf.multi_cell(
        0,
        4,
        f"Litros estimados = importe neto (EUR) / {eur_por_litro_ref:.2f} EUR/L. "
        f"Emisiones = litros x {kg_co2_por_litro:.2f} kg CO2eq/L.",
    )
    pdf.ln(2)

    pdf.set_font(body, "B", 9)
    pdf.cell(0, 6, "Totales acumulados", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 5, f"Litros diesel estimados: {litros_estimados_total:,.2f} L", ln=1)
    pdf.set_text_color(*EMERALD_600)
    pdf.set_font(body, "B", 10)
    pdf.cell(0, 7, f"Emisiones CO2 Scope 1: {co2_combustible_total_kg:,.2f} kg CO2eq", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.ln(2)

    pdf.set_font(body, "B", 9)
    pdf.cell(0, 6, "Desglose mensual", ln=1)
    pdf.set_fill_color(244, 244, 245)
    pdf.set_font(body, "B", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(45, 7, "Periodo", 1, 0, "L", True)
    pdf.cell(55, 7, "CO2 (kg)", 1, 0, "C", True)
    pdf.cell(55, 7, "Litros est.", 1, 0, "C", True)
    pdf.cell(35, 7, "Unidad", 1, 1, "C", True)
    pdf.set_font(body, "", 8)
    pdf.set_fill_color(255, 255, 255)

    if not meses:
        pdf.cell(0, 7, "Sin registros de combustible en el periodo.", ln=1)
    else:
        for m in meses:
            pdf.cell(45, 7, str(m.get("periodo", "")), 1)
            pdf.cell(55, 7, f"{float(m.get('co2_kg', 0)):,.3f}", 1, 0, "R")
            pdf.cell(55, 7, f"{float(m.get('litros_estimados', 0)):,.3f}", 1, 0, "R")
            pdf.cell(35, 7, "kg / L", 1, 1, "C")

    pdf.ln(6)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        "Documento informativo basado en datos de la plataforma. "
        "No sustituye informes auditados ni declaraciones regulatorias.",
    )

    # Pie: icono ecológico
    pdf.set_y(-22)
    draw_eco_footer_icon(pdf, pdf.w / 2 - 3, pdf.h - 18)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 4, "Compromiso con la eficiencia logística y el clima", align="C", ln=1)
    pdf.set_text_color(*ZINC_500)
    pdf.set_font(body, "", 7)
    pdf.cell(
        0,
        4,
        f"Generado {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | AB Logistics OS",
        align="C",
        ln=1,
    )

    return _pdf_output_bytes(pdf)


def generar_pdf_certificado_ruta_esg(
    *,
    distancia_km: float,
    toneladas_carga: float,
    tipo_combustible: str,
    consumo_litros_100km: float,
    emisiones_kg: float,
    ahorro_kg: float,
    factor_tkm: float | None = None,
) -> bytes:
    """Certificado PDF de simulación de ruta — diploma + fórmula km × t × factor."""
    import os as _os

    f_tkm = float(factor_tkm if factor_tkm is not None else (_os.getenv("ECO_FACTOR_HUELLA_PORTE_KG_CO2_TKM") or "0.062"))
    modelo_kg = float(distancia_km) * float(toneladas_carga) * f_tkm

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=24)
    body, mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    pdf.set_draw_color(*EMERALD_600)
    pdf.set_line_width(0.9)
    pdf.rect(11, 9, pdf.w - 22, pdf.h - 26, "D")
    pdf.set_draw_color(*ZINC_200)
    pdf.set_line_width(0.25)
    pdf.rect(13, 11, pdf.w - 26, pdf.h - 30, "D")

    pdf.set_y(16)
    pdf.set_font(body, "B", 13)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 8, "DIPLOMA DE SOSTENIBILIDAD", align="C", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, "AB Logistics OS | Certificado de huella de ruta", align="C", ln=1)
    pdf.ln(6)

    pdf.set_font(body, "B", 11)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 8, "Cálculo de huella (modelo t km)", align="C", ln=1)
    pdf.set_font(mono, "", 9)
    pdf.set_text_color(*ZINC_800)
    km_s = f"{float(distancia_km):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    t_s = f"{float(toneladas_carga):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    f_s = f"{f_tkm:.4f}"
    res_s = f"{modelo_kg:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    eq = f"{km_s} km x {t_s} t x {f_s} kg/(t km) = {res_s} kg CO2eq"
    pdf.multi_cell(0, 5, eq, align="C")
    pdf.ln(4)

    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 6, f"Motorización: {tipo_combustible.upper()} | Consumo ref.: {consumo_litros_100km} L/100km", align="C", ln=1)
    pdf.ln(3)

    pdf.set_fill_color(236, 253, 245)
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 7, "Resultados de referencia (simulación)", ln=1)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 6, f"Emisiones estimadas (motor de ruta): {emisiones_kg:,.2f} kg CO2", ln=1)
    pdf.cell(0, 6, f"Ahorro vs. referencia tradicional: {ahorro_kg:,.2f} kg CO2", ln=1)
    pdf.ln(4)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        "El motor de ruta puede combinar consumo y factores de combustible; "
        "la igualdad con el modelo t km no está garantizada en todos los escenarios.",
        align="C",
    )

    pdf.set_y(-24)
    draw_eco_footer_icon(pdf, pdf.w / 2 - 3, pdf.h - 19)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 4, "Sostenibilidad | Logística responsable", align="C", ln=1)

    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.set_text_color(*ZINC_500)
    pdf.set_font(body, "", 7)
    pdf.cell(0, 4, f"Emitido {fecha_hoy} | AB Logistics OS", align="C", ln=1)

    return _pdf_output_bytes(pdf)


