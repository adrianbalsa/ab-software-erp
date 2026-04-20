from __future__ import annotations

import io
import asyncio
import json
import os
from typing import Any
from uuid import UUID
from datetime import datetime, timezone
from pathlib import Path

import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
try:
    from weasyprint import HTML
except ModuleNotFoundError:  # pragma: no cover - handled in runtime/tests
    HTML = None  # type: ignore[assignment]

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE
from app.db.supabase import SupabaseAsync
from app.core.crypto import pii_crypto

# Paleta Enterprise (RGB 0–1 para ReportLab)
AB_PRIMARY = colors.HexColor("#2563eb")
AB_BG = colors.HexColor("#0b1224")
AB_MUTED = colors.HexColor("#64748b")

# Referencia diésel certificada (ISO 14083 — alineada con ``app.core.constants``).
KG_CO2_POR_LITRO_EURO6_REF = float(
    os.getenv("ESG_CO2_KG_PER_L_EURO6_REF") or str(ISO_14083_DIESEL_CO2_KG_PER_LITRE)
)
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _parse_porte_lineas_snapshot(raw: Any) -> list[dict[str, Any]]:
    """Única fuente de líneas del PDF: columna inmutable de `facturas`."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [dict(x) if isinstance(x, dict) else {} for x in raw]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return [dict(x) for x in data] if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _build_validation_url_qr(*, factura_id: str, hash_registro: str | None) -> str:
    """URL de validación (QR y pie de página)."""
    base = (os.getenv("VERIFACTU_VALIDATION_BASE_URL") or "").strip().rstrip("/")
    if not base:
        base = "https://validar.ablogistics.local"
    from urllib.parse import quote

    h = (hash_registro or "").strip()
    q = f"factura_id={quote(factura_id)}"
    if h:
        q += f"&hash_registro={quote(h)}"
    return f"{base}/verificar?{q}"


def render_factura_inmutable_pdf_sync(
    *,
    factura_row: dict[str, Any],
    empresa_nombre: str,
    cliente_nombre: str,
    nif_cliente: str,
) -> bytes:
    """
    PDF corporativo VeriFactu: **solo** `porte_lineas_snapshot` + totales de la fila `facturas`.
    """
    lineas = _parse_porte_lineas_snapshot(factura_row.get("porte_lineas_snapshot"))
    num = str(
        factura_row.get("num_factura") or factura_row.get("numero_factura") or ""
    )
    fecha = str(factura_row.get("fecha_emision") or "")[:10]
    raw_nif_emisor = str(factura_row.get("nif_emisor") or "")
    nif_emisor = pii_crypto.decrypt_pii(raw_nif_emisor) or raw_nif_emisor
    hash_reg = factura_row.get("hash_registro") or factura_row.get("hash_factura")
    hash_str = str(hash_reg or "").strip()
    fid = str(factura_row.get("id") or "")

    base_imp = float(factura_row.get("base_imponible") or 0.0)
    cuota = float(factura_row.get("cuota_iva") or 0.0)
    total = float(factura_row.get("total_factura") or (base_imp + cuota))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Factura {num}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="AbTitle",
        parent=styles["Heading1"],
        textColor=AB_PRIMARY,
        fontSize=18,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    sub_style = ParagraphStyle(
        name="AbSub",
        parent=styles["Normal"],
        textColor=AB_MUTED,
        fontSize=9,
        spaceAfter=14,
    )
    story: list[Any] = []

    story.append(Paragraph("AB Logistics OS", title_style))
    story.append(Paragraph("Factura VeriFactu · documento inmutable", sub_style))

    story.append(Paragraph(f"<b>Factura:</b> {num}", styles["Normal"]))
    story.append(Paragraph(f"<b>Fecha emisión:</b> {fecha}", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"<b>Emisor</b> · {empresa_nombre}", styles["Normal"]))
    story.append(Paragraph(f"NIF: {nif_emisor}", styles["Normal"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"<b>Cliente</b> · {cliente_nombre}", styles["Normal"]))
    raw_nif_cliente = str(nif_cliente or "")
    nif_cliente_plain = pii_crypto.decrypt_pii(raw_nif_cliente) or raw_nif_cliente
    story.append(Paragraph(f"NIF: {nif_cliente_plain or '—'}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("<b>Detalle (snapshot fiscal, no datos vivos de portes)</b>", styles["Heading2"]))
    story.append(Spacer(1, 2 * mm))

    table_data: list[list[str]] = [
        ["Concepto", "Km", "Base EUR"],
    ]
    for ln in lineas:
        orig = str(ln.get("origen") or "")
        dst = str(ln.get("destino") or "")
        fd = str(ln.get("fecha") or "")[:10]
        desc = str(ln.get("descripcion") or "")
        concepto = f"{fd} {orig} → {dst}"
        if desc:
            concepto += f" · {desc[:60]}"
        km = float(ln.get("km_estimados") or 0.0)
        precio = float(ln.get("precio_pactado") or 0.0)
        table_data.append([concepto[:72], f"{km:.1f}", f"{precio:.2f}"])

    if len(table_data) == 1:
        table_data.append(["(Sin líneas en snapshot — verificar migración Fase 2)", "—", "—"])

    t = Table(table_data, colWidths=[100 * mm, 22 * mm, 32 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AB_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    tot_data = [
        ["Base imponible", f"{base_imp:.2f} EUR"],
        ["Cuota IVA", f"{cuota:.2f} EUR"],
        ["Total", f"{total:.2f} EUR"],
    ]
    tt = Table(tot_data, colWidths=[120 * mm, 40 * mm])
    tt.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), AB_PRIMARY),
                ("LINEABOVE", (0, -1), (-1, -1), 1, AB_PRIMARY),
            ]
        )
    )
    story.append(tt)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("<b>Huella SHA-256 (VeriFactu)</b>", styles["Heading2"]))
    hash_para_pdf = hash_str if len(hash_str) <= 120 else hash_str[:60] + "…" + hash_str[-20:]
    story.append(
        Paragraph(
            f'<font face="Courier" size="8">{hash_para_pdf or "—"}</font>',
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    url_qr = _build_validation_url_qr(factura_id=fid, hash_registro=hash_str or None)
    qr_buf = io.BytesIO()
    qrcode.make(url_qr, border=1).save(qr_buf, format="PNG")
    qr_buf.seek(0)
    story.append(Paragraph("<b>Validación</b> · escanee el código QR", styles["Normal"]))
    story.append(Spacer(1, 2 * mm))
    story.append(RLImage(qr_buf, width=36 * mm, height=36 * mm))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f'<font size="7" color="#64748b">{url_qr}</font>',
            styles["Normal"],
        )
    )

    doc.build(story)
    out = buf.getvalue()
    buf.close()
    return out


def render_certificado_huella_co2_sync(
    *,
    empresa_nombre: str,
    periodo: str,
    co2_kg_mes: float,
    litros_estimados: float,
) -> bytes:
    """
    Certificado de huella Scope 1 (combustible) para un periodo YYYY-MM.
    Referencia normativa diésel ISO 14083: kg CO₂eq/L sobre litros estimados.
    """
    co2_referencia_euro6 = max(0.0, litros_estimados * KG_CO2_POR_LITRO_EURO6_REF)
    co2_declarado = max(0.0, float(co2_kg_mes))
    ahorro_vs_euro6 = max(0.0, co2_referencia_euro6 - co2_declarado)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Huella CO2 {periodo}")
    styles = getSampleStyleSheet()
    story: list[Any] = []
    story.append(Paragraph("<b>Certificado de huella de carbono (Scope 1)</b>", styles["Title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Empresa: <b>{empresa_nombre}</b>", styles["Normal"]))
    story.append(Paragraph(f"Periodo: <b>{periodo}</b>", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("<b>Resultados (metodología combustible)</b>", styles["Heading2"]))
    story.append(Paragraph(f"Emisiones CO₂ declaradas (periodo): <b>{co2_kg_mes:.3f} kg</b>", styles["Normal"]))
    story.append(Paragraph(f"Litros estimados (combustible): <b>{litros_estimados:.3f} L</b>", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            f"Referencia normativa diésel ISO 14083 (factor {KG_CO2_POR_LITRO_EURO6_REF} kg CO₂eq/L): "
            f"<b>{co2_referencia_euro6:.3f} kg CO₂</b>",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"Emisiones calculadas (metodología operativa interna): "
            f"<b>{co2_declarado:.3f} kg CO₂</b>",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"<font color='#2563eb'><b>Ahorro estimado vs referencia Euro 6: {ahorro_vs_euro6:.3f} kg CO₂</b></font>",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "<i>Documento informativo. No sustituye verificación de terceros ni registros oficiales.</i>",
            styles["Normal"],
        )
    )
    doc.build(story)
    out = buf.getvalue()
    buf.close()
    return out


class ReportService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def fetch_factura_for_empresa(
        self, *, empresa_id: str, factura_id: str
    ) -> dict[str, Any] | None:
        eid = str(empresa_id or "").strip()
        fid = str(factura_id or "").strip()
        if not eid or not fid:
            return None
        q = (
            self._db.table("facturas")
            .select("*")
            .eq("empresa_id", eid)
            .eq("id", fid)
            .limit(1)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return rows[0] if rows else None

    async def factura_inmutable_pdf_bytes(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
    ) -> bytes:
        row = await self.fetch_factura_for_empresa(empresa_id=empresa_id, factura_id=factura_id)
        if row is None:
            raise ValueError("Factura no encontrada")

        cliente_id = str(row.get("cliente") or "")
        emp_nombre = "AB Logistics"
        cli_nombre = cliente_id
        nif_cli = ""
        try:
            res_e: Any = await self._db.execute(
                self._db.table("empresas")
                .select("nombre_comercial, nombre_legal")
                .eq("id", str(empresa_id))
                .limit(1)
            )
            er = (res_e.data or []) if hasattr(res_e, "data") else []
            if er:
                r0 = er[0]
                emp_nombre = str(r0.get("nombre_comercial") or r0.get("nombre_legal") or emp_nombre)
        except Exception:
            pass
        if cliente_id:
            try:
                res_c: Any = await self._db.execute(
                    self._db.table("clientes").select("nombre, nif").eq("id", cliente_id).limit(1)
                )
                cr = (res_c.data or []) if hasattr(res_c, "data") else []
                if cr:
                    cli_nombre = str(cr[0].get("nombre") or cli_nombre)
                    nif_cli = str(cr[0].get("nif") or "")
            except Exception:
                pass

        def _run() -> bytes:
            return render_factura_inmutable_pdf_sync(
                factura_row=row,
                empresa_nombre=emp_nombre,
                cliente_nombre=cli_nombre,
                nif_cliente=nif_cli,
            )

        return await asyncio.to_thread(_run)

    async def certificado_huella_pdf_bytes(
        self,
        *,
        empresa_id: str | UUID,
        periodo: str,
        co2_kg_mes: float,
        litros_estimados: float,
    ) -> bytes:
        emp_nombre = "Empresa"
        eid = str(empresa_id).strip()
        try:
            res_e: Any = await self._db.execute(
                self._db.table("empresas")
                .select("nombre_comercial, nombre_legal")
                .eq("id", eid)
                .limit(1)
            )
            er = (res_e.data or []) if hasattr(res_e, "data") else []
            if er:
                r0 = er[0]
                emp_nombre = str(r0.get("nombre_comercial") or r0.get("nombre_legal") or emp_nombre)
        except Exception:
            pass

        def _run() -> bytes:
            return render_certificado_huella_co2_sync(
                empresa_nombre=emp_nombre,
                periodo=periodo,
                co2_kg_mes=co2_kg_mes,
                litros_estimados=litros_estimados,
            )

        return await asyncio.to_thread(_run)

    async def fleet_efficiency_pdf_bytes(
        self,
        *,
        empresa_id: str | UUID,
        advisor_context: dict[str, Any],
    ) -> bytes:
        eid = str(empresa_id).strip()
        empresa_nombre = "AB Logistics"
        try:
            res_e: Any = await self._db.execute(
                self._db.table("empresas")
                .select("nombre_comercial, nombre_legal")
                .eq("id", eid)
                .limit(1)
            )
            er = (res_e.data or []) if hasattr(res_e, "data") else []
            if er:
                r0 = er[0]
                empresa_nombre = str(r0.get("nombre_comercial") or r0.get("nombre_legal") or empresa_nombre)
        except Exception:
            pass

        def _to_float(v: Any) -> float | None:
            try:
                if v is None or v == "":
                    return None
                return float(v)
            except (TypeError, ValueError):
                return None

        def _to_money(v: Any) -> str:
            n = _to_float(v)
            if n is None:
                return "-"
            return f"{n:,.2f} EUR"

        def _to_num(v: Any, *, digits: int = 2) -> str:
            n = _to_float(v)
            if n is None:
                return "-"
            return f"{n:,.{digits}f}"

        bi = advisor_context.get("bi_intelligence") if isinstance(advisor_context, dict) else {}
        routes_raw = bi.get("routes_efficiency_below_1") if isinstance(bi, dict) else []
        routes: list[dict[str, Any]] = []
        total_emisiones_co2_kg = 0.0
        if isinstance(routes_raw, list):
            for i, row in enumerate(routes_raw, start=1):
                if not isinstance(row, dict):
                    continue
                eta = _to_float(row.get("efficiency_eta"))
                km_val = _to_float(row.get("km_estimados")) or 0.0
                emisiones = round((km_val * 750.0) / 1000.0, 2)
                total_emisiones_co2_kg += emisiones
                routes.append(
                    {
                        "idx": i,
                        "route_label": str(row.get("route_label") or row.get("route") or f"Ruta #{i}"),
                        "cliente_nombre": str(row.get("cliente_nombre") or "-"),
                        "margen_eur": _to_money(row.get("margin_eur")),
                        "km_estimados": _to_num(km_val),
                        "efficiency_eta": _to_num(eta, digits=4),
                        "emisiones_co2_kg": f"{emisiones:,.1f} kg",
                        "is_vampire": bool(eta is not None and eta < 1.0),
                    }
                )

        dashboard = advisor_context.get("cashflow_tesoreria") if isinstance(advisor_context, dict) else {}
        ebitda = advisor_context.get("ebitda_snapshot") if isinstance(advisor_context, dict) else {}
        cip_vampiros = advisor_context.get("cip_vampiros") if isinstance(advisor_context, dict) else []
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        template = _jinja_env.get_template("efficiency_report.html")
        rendered_html = template.render(
            empresa_id=eid,
            empresa_nombre=empresa_nombre,
            generated_at=generated_at,
            routes=routes,
            routes_total=len(routes),
            vampire_count=len([r for r in routes if r["is_vampire"]]),
            cip_vampiros_count=len(cip_vampiros) if isinstance(cip_vampiros, list) else 0,
            ingresos=ebitda.get("ingresos_netos_sin_iva_eur") if isinstance(ebitda, dict) else None,
            gastos=ebitda.get("gastos_netos_sin_iva_eur") if isinstance(ebitda, dict) else None,
            ebitda=ebitda.get("ebitda_aprox_sin_iva_eur") if isinstance(ebitda, dict) else None,
            margen_km=dashboard.get("margen_km_eur") if isinstance(dashboard, dict) else None,
            km_mes=dashboard.get("km_facturados_mes_actual") if isinstance(dashboard, dict) else None,
            total_emisiones_co2_kg=f"{total_emisiones_co2_kg:,.1f} kg",
        )

        def _run() -> bytes:
            if HTML is None:
                raise RuntimeError("WeasyPrint no esta instalado en el entorno actual")
            return HTML(string=rendered_html).write_pdf()

        return await asyncio.to_thread(_run)
