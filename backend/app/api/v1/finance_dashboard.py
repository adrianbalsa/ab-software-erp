from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api import deps
from app.core.pdf_generator import generate_esg_certificate
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.finance import EsgMonthlyReportOut, TreasuryRiskDashboardOut, TreasuryRiskTrendPointOut
from app.schemas.user import UserOut

router = APIRouter()


def _month_key(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return None


def _last_n_month_keys(*, today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out: list[str] = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    out.reverse()
    return out


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "si"}


def _risk_score_from_credit(*, limite_credito: float, pending_amount: float, persisted_score: float | None) -> float:
    # Prefer persisted risk score when available.
    if persisted_score is not None:
        return persisted_score
    if limite_credito <= 0:
        return 10.0 if pending_amount > 0 else 0.0
    ratio = pending_amount / limite_credito
    # Heuristic scale [0..10] from pending/limit ratio.
    return max(0.0, min(10.0, ratio * 10.0))


def _current_period(today: date) -> tuple[str, str, str]:
    start = today.replace(day=1).isoformat()
    period = today.strftime("%Y-%m")
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return period, start, next_month.isoformat()


@router.get(
    "/treasury-risk",
    response_model=TreasuryRiskDashboardOut,
    summary="KPIs de tesorería y riesgo de cobro (6 meses)",
)
async def treasury_risk_dashboard(
    current_user: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> TreasuryRiskDashboardOut:
    empresa_id = str(current_user.empresa_id)
    months = _last_n_month_keys(today=date.today(), n=6)
    trend_raw: dict[str, dict[str, float]] = {m: {"cobrado": 0.0, "pendiente": 0.0} for m in months}

    res_facturas: Any = await db.execute(
        db.table("facturas").select("cliente, total_factura, estado_cobro, fecha_emision").eq("empresa_id", empresa_id)
    )
    facturas_rows: list[dict[str, Any]] = (res_facturas.data or []) if hasattr(res_facturas, "data") else []

    use_portes_fallback = len(facturas_rows) == 0
    pending_by_client: dict[str, float] = {}

    if not use_portes_fallback:
        for row in facturas_rows:
            client_id = str(row.get("cliente") or "").strip()
            amount = max(0.0, _to_float(row.get("total_factura")))
            status = str(row.get("estado_cobro") or "").strip().lower()
            is_paid = status == "cobrada"

            mk = _month_key(row.get("fecha_emision"))
            if mk in trend_raw:
                if is_paid:
                    trend_raw[mk]["cobrado"] += amount
                else:
                    trend_raw[mk]["pendiente"] += amount

            if not is_paid and client_id:
                pending_by_client[client_id] = pending_by_client.get(client_id, 0.0) + amount
    else:
        res_portes: Any = await db.execute(
            filter_not_deleted(
                db.table("portes")
                .select("cliente_id, precio_pactado, fecha, estado")
                .eq("empresa_id", empresa_id)
            )
        )
        portes_rows: list[dict[str, Any]] = (res_portes.data or []) if hasattr(res_portes, "data") else []

        for row in portes_rows:
            client_id = str(row.get("cliente_id") or "").strip()
            amount = max(0.0, _to_float(row.get("precio_pactado")))
            estado = str(row.get("estado") or "").strip().lower()
            # Sin factura emitida: todo lo no facturado se considera pendiente comercial.
            is_pending = estado != "facturado"

            mk = _month_key(row.get("fecha"))
            if mk in trend_raw:
                if is_pending:
                    trend_raw[mk]["pendiente"] += amount
                else:
                    trend_raw[mk]["cobrado"] += amount

            if is_pending and client_id:
                pending_by_client[client_id] = pending_by_client.get(client_id, 0.0) + amount

    cliente_ids = list(pending_by_client.keys())
    clientes_by_id: dict[str, dict[str, Any]] = {}
    if cliente_ids:
        try:
            res_clientes: Any = await db.execute(
                filter_not_deleted(
                    db.table("clientes")
                    .select("id, mandato_activo, limite_credito, riesgo_score")
                    .eq("empresa_id", empresa_id)
                    .in_("id", cliente_ids)
                )
            )
        except Exception:
            # Compatibilidad si `riesgo_score` no existe todavía.
            res_clientes = await db.execute(
                filter_not_deleted(
                    db.table("clientes")
                    .select("id, mandato_activo, limite_credito")
                    .eq("empresa_id", empresa_id)
                    .in_("id", cliente_ids)
                )
            )
        rows = (res_clientes.data or []) if hasattr(res_clientes, "data") else []
        clientes_by_id = {str(r.get("id") or "").strip(): r for r in rows}

    total_pendiente = round(sum(pending_by_client.values()), 2)
    garantizado_sepa = 0.0
    en_riesgo_alto = 0.0

    for cid, pending in pending_by_client.items():
        c = clientes_by_id.get(cid, {})
        if _to_bool(c.get("mandato_activo")):
            garantizado_sepa += pending

        limite_credito = _to_float(c.get("limite_credito"))
        persisted_score_raw = c.get("riesgo_score")
        persisted_score = _to_float(persisted_score_raw) if persisted_score_raw is not None else None
        risk = _risk_score_from_credit(
            limite_credito=limite_credito,
            pending_amount=pending,
            persisted_score=persisted_score,
        )
        if risk > 7.0:
            en_riesgo_alto += pending

    trend = [
        TreasuryRiskTrendPointOut(
            periodo=mk,
            cobrado=round(trend_raw[mk]["cobrado"], 2),
            pendiente=round(trend_raw[mk]["pendiente"], 2),
        )
        for mk in months
    ]

    return TreasuryRiskDashboardOut(
        total_pendiente=round(total_pendiente, 2),
        garantizado_sepa=round(garantizado_sepa, 2),
        en_riesgo_alto=round(en_riesgo_alto, 2),
        cashflow_trend=trend,
        fuente_datos="portes" if use_portes_fallback else "facturas",
    )


@router.get(
    "/esg-report",
    response_model=EsgMonthlyReportOut,
    summary="Reporte mensual ESG de huella de carbono",
)
async def monthly_esg_report(
    current_user: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> EsgMonthlyReportOut:
    report_data = await _build_esg_monthly_report_data(
        db=db,
        empresa_id=str(current_user.empresa_id),
    )
    return EsgMonthlyReportOut(
        periodo=str(report_data["periodo"]),
        total_co2_kg=float(report_data["total_co2_kg"]),
        total_portes=int(report_data["total_portes"]),
    )


async def _build_esg_monthly_report_data(*, db: SupabaseAsync, empresa_id: str) -> dict[str, Any]:
    empresa_id = str(empresa_id)
    today = date.today()
    period, month_start, next_month_start = _current_period(today)

    rows: list[dict[str, Any]] = []
    try:
        res: Any = await db.execute(
            filter_not_deleted(
                db.table("portes")
                .select("co2_kg, co2_emitido, km_estimados, fecha")
                .eq("empresa_id", empresa_id)
                .gte("fecha", month_start)
                .lt("fecha", next_month_start)
            )
        )
        rows = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        rows = []

    total = 0.0
    total_km = 0.0
    for row in rows:
        # Prioridad: nuevo campo co2_kg; fallback a co2_emitido o factor estándar.
        raw = row.get("co2_kg")
        if raw is None:
            raw = row.get("co2_emitido")
        if raw is None:
            total += max(0.0, _to_float(row.get("km_estimados"))) * 0.62
        else:
            total += max(0.0, _to_float(raw))
        total_km += max(0.0, _to_float(row.get("km_estimados")))

    empresa_nombre = "AB Logistics OS"
    try:
        res_emp: Any = await db.execute(
            db.table("empresas").select("nombre_comercial,nombre_legal").eq("id", empresa_id).limit(1)
        )
        emp_rows = (res_emp.data or []) if hasattr(res_emp, "data") else []
        if emp_rows:
            row0 = emp_rows[0]
            empresa_nombre = (
                str(row0.get("nombre_comercial") or "").strip()
                or str(row0.get("nombre_legal") or "").strip()
                or empresa_nombre
            )
    except Exception:
        pass

    return {
        "periodo": period,
        "total_co2_kg": round(total, 6),
        "total_portes": len(rows),
        "total_km": round(total_km, 3),
        "empresa_nombre": empresa_nombre,
    }


@router.get(
    "/esg-report/download",
    summary="Descargar certificado ESG mensual en PDF",
)
async def monthly_esg_report_download(
    current_user: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> StreamingResponse:
    report_data = await _build_esg_monthly_report_data(
        db=db,
        empresa_id=str(current_user.empresa_id),
    )
    pdf_bytes = generate_esg_certificate(report_data)
    period = str(report_data.get("periodo") or date.today().strftime("%Y-%m"))
    filename = f"certificado_esg_{period}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
