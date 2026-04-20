from __future__ import annotations

import base64
import datetime
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image

from app.core.i18n import get_translator
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
    raw = pdf.output()
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    if raw is None:
        return b""
    return str(raw).encode("latin-1")


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

    def __init__(self, tr: Callable[[str], str] | None = None) -> None:
        super().__init__()
        self.body_family = "helvetica"
        self.mono_family = "courier"
        self._tr: Callable[[str], str] = tr if tr is not None else (lambda s: s)
        self.set_auto_page_break(auto=True, margin=18)

    def header(self) -> None:
        logo = _BACKEND_ROOT / "assets" / "logo.png"
        if logo.is_file():
            self.image(str(logo), x=12, y=10, w=32)

        self.set_xy(12, 12)
        self.set_font(self.body_family, "B", 18)
        self.set_text_color(*EMERALD_600)
        self.cell(0, 8, self._tr("AB Logistics OS"), align="R")
        self.ln(6)
        self.set_font(self.body_family, "B", 14)
        self.set_text_color(*ZINC_800)
        self.cell(0, 7, self._tr("Invoice"), align="R")
        self.ln(12)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(self.body_family, "", 8)
        self.set_text_color(*ZINC_500)
        self.cell(0, 5, self._tr("Page {n}").format(n=self.page_no()), align="C")


def generar_pdf_factura(
    datos_empresa: dict[str, Any],
    datos_cliente: dict[str, Any],
    conceptos: list[dict[str, Any]],
    *,
    lang: str | None = None,
) -> bytes:
    """
    PDF de factura con rejilla moderna, sección VeriFactu y fuentes de marca (Roboto / Roboto Mono).

    ``datos_empresa`` puede incluir (opcional): ``numero_factura``, ``fecha_emision``, ``num_factura``,
    ``base_imponible``, ``cuota_iva``, ``total_factura``, ``iva_porcentaje``, ``hash``.
    """
    t = get_translator(lang)
    pdf = InvoicePDF(tr=t)
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
    pdf.cell(95, 5, f"{t('Document no.')} {num}", align="L")
    pdf.cell(95, 5, f"{t('Issue date')}: {fecha}", align="R")
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
        f"{t('Tax ID')}: {str(datos_empresa.get('nif') or '').strip() or '—'}",
    ]
    re_lines = [
        str(datos_cliente.get("nombre") or ""),
        f"{t('Tax ID')}: {str(datos_cliente.get('nif') or '').strip() or '—'}",
        f"{t('Customer ref.')}: {datos_cliente.get('id', '')}",
    ]

    pdf.set_xy(pdf.l_margin, y0)
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(half, 6, t("Issuer"), border="LTR", align="L", fill=True)
    pdf.set_xy(pdf.l_margin + half + 4, y0)
    pdf.cell(half, 6, t("Recipient"), border="LTR", align="L", fill=True)
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
    pdf.cell(
        118,
        8,
        t("Service / line item"),
        border=1,
        align="L",
        fill=True,
        new_x=XPos.RIGHT,
        new_y=YPos.TOP,
    )
    pdf.cell(
        65,
        8,
        t("Amount (EUR)"),
        border=1,
        align="R",
        fill=True,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

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
        pdf.cell(118, 8, nombre, border=1, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(
            65,
            8,
            _fmt_eur(precio),
            border=1,
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

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
    pdf.cell(118, 6, "", border=0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    if iva_pct is not None:
        pdf.cell(
            65,
            6,
            t("Taxable base: {amt}").format(amt=_fmt_eur(base)),
            border=0,
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.cell(118, 6, "", border=0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(
            65,
            6,
            t("VAT ({pct}%): {amt}").format(pct=iva_pct, amt=_fmt_eur(cuota)),
            border=0,
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    else:
        pdf.cell(
            65,
            6,
            t("Base: {amt}").format(amt=_fmt_eur(base)),
            border=0,
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        if cuota is not None:
            pdf.cell(118, 6, "", border=0, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(
                65,
                6,
                t("VAT amount: {amt}").format(amt=_fmt_eur(cuota)),
                border=0,
                align="R",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(118, 8, "", border=0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        65,
        8,
        t("Total {amt}").format(amt=_fmt_eur(total)),
        border=0,
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

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
    pdf.cell(
        text_col_w - 6,
        5,
        t("VeriFactu evidence"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.set_x(pdf.l_margin + 3)
    pdf.multi_cell(
        text_col_w - 6,
        4,
        t("Record ID: {num}\nSHA-256 fingerprint (SIF chain):").format(num=num_vf),
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
            pdf.multi_cell(qr_w_mm, 4, t("VeriFactu QR\n(unavailable)"), align="C")

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
    lang: str | None = None,
) -> bytes:
    """
    Certificado mensual Scope 1 (combustible) — estilo diploma de sostenibilidad.

    Muestra el modelo de huella transporte: km x t x factor = kg CO2eq (referencia metodológica)
    y el desglose de datos registrados (combustible).
    """
    import os as _os

    t = get_translator(lang)
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
    pdf.cell(0, 8, t("Sustainability diploma"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, t("CO2 emissions — methodology reference and recorded data"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font(body, "B", 12)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 10, t("Emissions certificate (Scope 1 | fuel)"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.multi_cell(
        0,
        5,
        f"{t('Company')}: {empresa_nombre}\n{t('Audit ID')}: {empresa_id}",
    )
    pdf.ln(3)

    # Fórmula hero (modelo transporte)
    pdf.set_fill_color(236, 253, 245)
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_text_color(*ZINC_800)
    pdf.set_font(body, "B", 9)
    pdf.cell(0, 7, t("Transport footprint model (t km)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    formula = t(
        "km × tonnes × factor = kg CO2eq  =>  reference factor = {f} kg CO2 / (t km)"
    ).format(f=f"{f_tkm:.4f}")
    pdf.multi_cell(0, 5, formula)
    pdf.ln(2)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "This expression describes the ESG port model on the platform. Totals below come from expenses classified as FUEL (diesel)."
        ),
    )
    pdf.ln(3)

    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 7, t("Fuel methodology (Scope 1)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 8)
    pdf.multi_cell(
        0,
        4,
        t(
            "Estimated litres = net amount (EUR) / {eur} EUR/L. Emissions = litres × {kg} kg CO2eq/L."
        ).format(eur=f"{eur_por_litro_ref:.2f}", kg=f"{kg_co2_por_litro:.2f}"),
    )
    pdf.ln(2)

    pdf.set_font(body, "B", 9)
    pdf.cell(0, 6, t("Running totals"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    lit_s = f"{litros_estimados_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    pdf.cell(0, 5, t("Estimated diesel litres: {v} L").format(v=lit_s), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*EMERALD_600)
    pdf.set_font(body, "B", 10)
    co2_s = f"{co2_combustible_total_kg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    pdf.cell(0, 7, t("Scope 1 CO2 emissions: {v} kg CO2eq").format(v=co2_s), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.ln(2)

    pdf.set_font(body, "B", 9)
    pdf.cell(0, 6, t("Monthly breakdown"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(244, 244, 245)
    pdf.set_font(body, "B", 8)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(45, 7, t("Period"), border=1, align="L", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(55, 7, t("CO2 (kg)"), border=1, align="C", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(55, 7, t("Est. litres"), border=1, align="C", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(35, 7, t("Unit"), border=1, align="C", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 8)
    pdf.set_fill_color(255, 255, 255)

    if not meses:
        pdf.cell(0, 7, t("No fuel records in the period."), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        for m in meses:
            pdf.cell(45, 7, str(m.get("periodo", "")), border=1)
            pdf.cell(
                55,
                7,
                f"{float(m.get('co2_kg', 0)):,.3f}",
                border=1,
                align="R",
                new_x=XPos.RIGHT,
                new_y=YPos.TOP,
            )
            pdf.cell(
                55,
                7,
                f"{float(m.get('litros_estimados', 0)):,.3f}",
                border=1,
                align="R",
                new_x=XPos.RIGHT,
                new_y=YPos.TOP,
            )
            pdf.cell(35, 7, t("kg / L"), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(6)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "Informational document based on platform data. Does not replace audited reports or regulatory filings."
        ),
    )

    # Pie: icono ecológico
    pdf.set_y(-22)
    draw_eco_footer_icon(pdf, pdf.w / 2 - 3, pdf.h - 18)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 4, t("Commitment to logistics efficiency and climate"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*ZINC_500)
    pdf.set_font(body, "", 7)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(
        0,
        4,
        t("Generated {ts} | AB Logistics OS").format(ts=ts),
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
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
    lang: str | None = None,
) -> bytes:
    """Certificado PDF de simulación de ruta — diploma + fórmula km × t × factor."""
    import os as _os

    t = get_translator(lang)
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
    pdf.cell(0, 8, t("Sustainability diploma"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, t("AB Logistics OS | Route footprint certificate"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    pdf.set_font(body, "B", 11)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 8, t("Footprint calculation (t km model)"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
    pdf.cell(
        0,
        6,
        t("Powertrain: {motor} | Ref. consumption: {l} L/100km").format(
            motor=tipo_combustible.upper(),
            l=consumo_litros_100km,
        ),
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(3)

    pdf.set_fill_color(236, 253, 245)
    pdf.set_draw_color(*EMERALD_600)
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 7, t("Reference results (simulation)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_800)
    em_s = f"{emisiones_kg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    ah_s = f"{ahorro_kg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    pdf.cell(0, 6, t("Estimated emissions (route engine): {v} kg CO2").format(v=em_s), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, t("Savings vs traditional reference: {v} kg CO2").format(v=ah_s), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font(body, "", 8)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "The route engine may combine consumption and fuel factors; equality with the t km model is not guaranteed in all scenarios."
        ),
        align="C",
    )

    pdf.set_y(-24)
    draw_eco_footer_icon(pdf, pdf.w / 2 - 3, pdf.h - 19)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 4, t("Sustainability | Responsible logistics"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.set_text_color(*ZINC_500)
    pdf.set_font(body, "", 7)
    pdf.cell(0, 4, t("Issued {ts} | AB Logistics OS").format(ts=fecha_hoy), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return _pdf_output_bytes(pdf)


def _strip_data_url_b64(raw: str) -> str:
    s = str(raw or "").strip()
    if s.startswith("data:") and "," in s:
        return s.split(",", 1)[1].strip()
    return s


def _fmt_firma_entrega_exacta(iso_s: str) -> str:
    """Fecha/hora legible en UTC para el pie de firma del POD."""
    try:
        s = str(iso_s).strip().replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%d/%m/%Y %H:%M:%S") + " UTC"
    except Exception:
        return str(iso_s)[:48]


def generar_albaran_entrega_pdf(
    *,
    datos_empresa: dict[str, Any],
    datos_porte: dict[str, Any],
    nombre_consignatario: str,
    firma_b64: str,
    fecha_entrega_iso: str,
    dni_consignatario: str | None = None,
    lang: str | None = None,
) -> bytes:
    """
    Albarán de entrega digital (POD) con firma incrustada (PNG Base64).
    """
    t = get_translator(lang)
    raw_b64 = _strip_data_url_b64(firma_b64)
    try:
        img_bytes = base64.b64decode(raw_b64, validate=True)
    except Exception as e:
        raise ValueError(t("Invalid signature Base64")) from e

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    body, _mono = register_brand_fonts(pdf)
    pdf.add_page()
    pdf.set_margin(14)

    em = str(datos_empresa.get("nombre_comercial") or datos_empresa.get("nombre_legal") or "—")
    nif_em = str(datos_empresa.get("nif") or "—")

    origen = str(datos_porte.get("origen") or "—")
    destino = str(datos_porte.get("destino") or "—")
    desc = str(datos_porte.get("descripcion") or "—")
    try:
        bultos = int(datos_porte.get("bultos") or 0)
    except (TypeError, ValueError):
        bultos = 0
    pid = str(datos_porte.get("id") or "—")

    pdf.set_font(body, "B", 16)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 10, t("Bill of lading / Proof of delivery (POD)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.set_text_color(*ZINC_500)
    pdf.cell(0, 5, t("Shipment {pid} | AB Logistics OS").format(pid=pid), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 6, t("Carrier"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.multi_cell(0, 5, f"{em}\nNIF: {nif_em}")
    pdf.ln(2)

    pdf.set_font(body, "B", 10)
    pdf.cell(0, 6, t("Delivery"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(body, "", 9)
    pdf.multi_cell(
        0,
        5,
        t("Origin: {o}\nDestination: {d}\nGoods: {g}\nPackages: {b}").format(
            o=origen, d=destino, g=desc, b=bultos
        ),
    )
    pdf.ln(4)

    pdf.set_font(body, "B", 10)
    pdf.set_text_color(*ZINC_800)
    pdf.cell(0, 6, t("Consignee signature"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    y_img = pdf.get_y()
    max_w = min(120.0, float(pdf.w - 28))
    display_h = 40.0
    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            w_px, h_px = im.size
            if w_px > 0 and h_px > 0:
                display_h = max_w * (float(h_px) / float(w_px))
        pdf.image(io.BytesIO(img_bytes), x=14, y=y_img, w=max_w, type="PNG")
    except Exception:
        pdf.set_font(body, "", 8)
        pdf.set_text_color(180, 0, 0)
        pdf.multi_cell(0, 4, t("(Could not embed signature image.)"))
        display_h = 8.0

    pdf.set_y(y_img + display_h + 5)
    fecha_txt = _fmt_firma_entrega_exacta(fecha_entrega_iso)
    dni = (dni_consignatario or "").strip()
    dni_part = t(" (ID {dni})").format(dni=dni) if dni else ""
    linea_firma = t("Signed by: {name}{dni} on {when}").format(
        name=nombre_consignatario, dni=dni_part, when=fecha_txt
    )
    pdf.set_font(body, "B", 9)
    pdf.set_text_color(*ZINC_800)
    pdf.multi_cell(0, 5, linea_firma)

    pdf.ln(6)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*ZINC_500)
    pdf.multi_cell(
        0,
        4,
        t(
            "Electronically generated document. The signature reproduces the stroke captured on the recipient device. Keep this POD as proof of delivery."
        ),
        align="L",
    )
    pdf.set_y(-12)
    pdf.set_font(body, "", 7)
    pdf.set_text_color(*EMERALD_600)
    pdf.cell(0, 4, t("AB Logistics OS — Digital delivery"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return _pdf_output_bytes(pdf)


