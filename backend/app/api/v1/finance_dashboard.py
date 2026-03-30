from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse

from app.api import deps
from app.core.pdf_generator import generate_esg_certificate
from app.models.webhook import WebhookEventType
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.finance_pending import aggregate_pending_and_trend
from app.schemas.finance import (
    CreditAlertOut,
    EsgMonthlyReportOut,
    RiskRankingRowOut,
    RouteMarginRowOut,
    TreasuryRiskDashboardOut,
    TreasuryRiskTrendPointOut,
    CIPMatrixPoint,
)
from app.services.portes_service import PortesService
from app.schemas.user import UserOut
from app.services.webhook_service import dispatch_webhook

router = APIRouter()


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


def _km_aplicable_porte(row: dict[str, Any]) -> float:
    """COALESCE(km_reales, km_estimados, 0) con km ≥ 0."""
    kr = row.get("km_reales")
    if kr is not None:
        return max(0.0, _to_float(kr))
    return max(0.0, _to_float(row.get("km_estimados")))


def _ruta_normalizada_key(row: dict[str, Any]) -> str | None:
    o = str(row.get("origen_ciudad") or row.get("origen") or "").strip()
    d = str(row.get("destino_ciudad") or row.get("destino") or "").strip()
    if not o and not d:
        return None
    return f"{o.upper()} - {d.upper()}"


def _ruta_display(row: dict[str, Any]) -> str:
    o = str(row.get("origen_ciudad") or row.get("origen") or "").strip()
    d = str(row.get("destino_ciudad") or row.get("destino") or "").strip()
    if not o and not d:
        return "—"
    return f"{o.title()} - {d.title()}"


async def _fetch_portes_para_margen_ruta(*, db: SupabaseAsync, empresa_id: str) -> list[dict[str, Any]]:
    """Lee portes no borrados; intenta incluir km_reales si existe en el esquema."""
    base = filter_not_deleted(
        db.table("portes")
        .select("origen, destino, origen_ciudad, destino_ciudad, precio_pactado, km_estimados, km_reales, estado")
        .eq("empresa_id", empresa_id)
    )
    try:
        res: Any = await db.execute(base)
    except Exception:
        res = await db.execute(
            filter_not_deleted(
                db.table("portes")
                .select("origen, destino, origen_ciudad, destino_ciudad, precio_pactado, km_estimados, estado")
                .eq("empresa_id", empresa_id)
            )
        )
    return (res.data or []) if hasattr(res, "data") else []

async def _fetch_portes_para_cip_matrix(*, db: SupabaseAsync, empresa_id: str) -> list[dict[str, Any]]:
    """Lee portes no borrados para Matriz CIP (con emisiones de CO2)."""
    base = filter_not_deleted(
        db.table("portes")
        .select("origen, destino, origen_ciudad, destino_ciudad, precio_pactado, km_estimados, km_reales, estado, co2_kg, co2_emitido")
        .eq("empresa_id", empresa_id)
    )
    try:
        res: Any = await db.execute(base)
    except Exception:
        res = await db.execute(
            filter_not_deleted(
                db.table("portes")
                .select("origen, destino, origen_ciudad, destino_ciudad, precio_pactado, km_estimados, estado")
                .eq("empresa_id", empresa_id)
            )
        )
    return (res.data or []) if hasattr(res, "data") else []


def _esg_texto_metodologia_certificado(*, counts: dict[str, int]) -> str:
    """
    Texto de pie para el PDF: metodología explícita (Mix Euro IV/V/VI) + desglose si hay datos de flota.
    """
    base = (
        "Emisiones calculadas según composición de flota (Mix Euro IV/V/VI). "
        "Cada porte aplica el factor de emisión correspondiente a la normativa EURO del vehículo asignado."
    )
    iv = int(counts.get("Euro IV", 0))
    v = int(counts.get("Euro V", 0))
    vi = int(counts.get("Euro VI", 0))
    if iv + v + vi <= 0:
        return base
    detalle = "; ".join(
        p
        for p in (
            f"Euro IV: {iv}" if iv else "",
            f"Euro V: {v}" if v else "",
            f"Euro VI: {vi}" if vi else "",
        )
        if p
    )
    return base + f" Desglose operativo por normativa en flota activa: {detalle}."


async def _flota_counts_normativa_euro(*, db: SupabaseAsync, empresa_id: str) -> dict[str, int]:
    eid = str(empresa_id or "").strip()
    out: dict[str, int] = defaultdict(int)
    if not eid:
        return dict(out)
    try:
        res: Any = await db.execute(
            filter_not_deleted(db.table("flota").select("normativa_euro").eq("empresa_id", eid))
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        return dict(out)
    for r in rows:
        n = str(r.get("normativa_euro") or "Euro VI").strip()
        if n in ("Euro IV", "Euro V", "Euro VI"):
            out[n] += 1
        else:
            out["Euro VI"] += 1
    return dict(out)


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


def _clamp_risk_score(value: float) -> float:
    return max(0.0, min(10.0, float(value)))


def _porcentaje_consumo_limite(*, saldo_pendiente: float, limite_credito: float) -> float:
    """
    (saldo / limite) * 100. Si ``limite_credito`` es 0 o negativo y hay saldo,
    se considera consumo 100 % (sin límite operativo definido).
    """
    saldo = max(0.0, float(saldo_pendiente))
    limite = float(limite_credito)
    if limite > 0:
        return (saldo / limite) * 100.0
    if saldo > 0:
        return 100.0
    return 0.0


@router.get(
    "/risk-ranking",
    response_model=list[RiskRankingRowOut],
    summary="Ranking de riesgo por cliente (V_r)",
)
async def risk_ranking_by_client(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> list[RiskRankingRowOut]:
    empresa_id = str(current_user.empresa_id)
    pending_by_client, _, _ = await aggregate_pending_and_trend(db, empresa_id, months_for_trend=None)

    try:
        res_clientes: Any = await db.execute(
            filter_not_deleted(
                db.table("clientes")
                .select("id, nombre, mandato_activo, limite_credito, riesgo_score")
                .eq("empresa_id", empresa_id)
            )
        )
    except Exception:
        res_clientes = await db.execute(
            filter_not_deleted(
                db.table("clientes")
                .select("id, nombre, mandato_activo, limite_credito")
                .eq("empresa_id", empresa_id)
            )
        )

    rows = (res_clientes.data or []) if hasattr(res_clientes, "data") else []
    ranked: list[RiskRankingRowOut] = []

    for row in rows:
        cid = str(row.get("id") or "").strip()
        if not cid:
            continue
        saldo = round(max(0.0, _to_float(pending_by_client.get(cid, 0.0))), 2)
        if saldo <= 0:
            continue

        limite_credito = _to_float(row.get("limite_credito"))
        persisted_raw = row.get("riesgo_score")
        persisted = _to_float(persisted_raw) if persisted_raw is not None else None
        score = _risk_score_from_credit(
            limite_credito=limite_credito,
            pending_amount=saldo,
            persisted_score=persisted,
        )
        score = _clamp_risk_score(score)
        valor_riesgo = round(saldo * (score / 10.0), 2)

        ranked.append(
            RiskRankingRowOut(
                cliente_id=cid,
                nombre=str(row.get("nombre") or "").strip() or "(sin nombre)",
                saldo_pendiente=saldo,
                riesgo_score=round(score, 2),
                valor_riesgo=valor_riesgo,
                mandato_sepa_activo=_to_bool(row.get("mandato_activo")),
            )
        )

    ranked.sort(key=lambda r: r.valor_riesgo, reverse=True)
    return ranked[:10]


@router.get(
    "/analytics/cip-matrix",
    response_model=list[CIPMatrixPoint],
    summary="Matriz CIP: Margen Neto vs. Emisiones de CO2 por ruta",
)
async def analytics_cip_matrix(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
    portes_service: PortesService = Depends(deps.get_portes_service),
) -> list[CIPMatrixPoint]:
    """
    Agrupa portes activos por ruta, calcula su margen neto y suma las emisiones de CO2.
    Solo incluye rutas con >= 2 portes para limpieza del gráfico.
    """
    empresa_id = str(current_user.empresa_id)
    coste_km = await portes_service.operational_cost_per_km_eur(empresa_id=empresa_id, default=1.10)

    rows = await _fetch_portes_para_cip_matrix(db=db, empresa_id=empresa_id)

    # Excluye cancelados explícitos; el resto de estados operativos entra.
    rows = [
        r
        for r in rows
        if str(r.get("estado") or "").strip().lower() != "cancelado"
    ]

    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _ruta_normalizada_key(row)
        if not key:
            continue
        
        ingreso = max(0.0, _to_float(row.get("precio_pactado")))
        km = _km_aplicable_porte(row)
        coste = km * coste_km
        
        # Emisiones CO2 logic: priority to co2_kg, then co2_emitido, then standard factor
        raw = row.get("co2_kg")
        if raw is None:
            raw = row.get("co2_emitido")
        if raw is None:
            emisiones = km * 0.62
        else:
            emisiones = max(0.0, _to_float(raw))

        if key not in buckets:
            buckets[key] = {
                "display": _ruta_display(row),
                "n": 0,
                "ingresos": 0.0,
                "costes": 0.0,
                "emisiones": 0.0,
            }
        b = buckets[key]
        b["n"] += 1
        b["ingresos"] += ingreso
        b["costes"] += coste
        b["emisiones"] += emisiones

    out: list[CIPMatrixPoint] = []
    for _k, b in buckets.items():
        n = int(b["n"])
        if n < 2:
            continue
        
        ing = float(b["ingresos"])
        cst = float(b["costes"])
        margen = round(ing - cst, 2)
        emi = round(float(b["emisiones"]), 6)
        
        out.append(
            CIPMatrixPoint(
                ruta=str(b["display"]),
                margen_neto=margen,
                emisiones_co2=emi,
                total_portes=n,
            )
        )

    out.sort(key=lambda r: r.margen_neto, reverse=True)
    return out


@router.get(
    "/margin-ranking",
    response_model=list[RouteMarginRowOut],
    summary="Ranking de margen neto por ruta (M_n), top 10",
)
async def margin_ranking_by_route(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
    portes_service: PortesService = Depends(deps.get_portes_service),
) -> list[RouteMarginRowOut]:
    """
    Agrupa portes activos (no borrados lógicamente) por ruta ``origen – destino`` normalizada
    (TRIM + UPPER). Coste operativo = km aplicables × coste €/km de empresa (default 1,10 si no hay dato).
    Solo rutas con ≥ 2 portes; orden por ``margen_neto`` descendente.
    """
    empresa_id = str(current_user.empresa_id)
    coste_km = await portes_service.operational_cost_per_km_eur(empresa_id=empresa_id, default=1.10)

    rows = await _fetch_portes_para_margen_ruta(db=db, empresa_id=empresa_id)

    # Excluye cancelados explícitos; el resto de estados operativos entra.
    rows = [
        r
        for r in rows
        if str(r.get("estado") or "").strip().lower() != "cancelado"
    ]

    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _ruta_normalizada_key(row)
        if not key:
            continue
        ingreso = max(0.0, _to_float(row.get("precio_pactado")))
        km = _km_aplicable_porte(row)
        coste = km * coste_km
        if key not in buckets:
            buckets[key] = {
                "display": _ruta_display(row),
                "n": 0,
                "ingresos": 0.0,
                "costes": 0.0,
            }
        b = buckets[key]
        b["n"] += 1
        b["ingresos"] += ingreso
        b["costes"] += coste

    out: list[RouteMarginRowOut] = []
    for _k, b in buckets.items():
        n = int(b["n"])
        if n < 2:
            continue
        ing = round(float(b["ingresos"]), 2)
        cst = round(float(b["costes"]), 2)
        margen = round(ing - cst, 2)
        pct = round((margen / ing) * 100.0, 2) if ing > 0 else 0.0
        out.append(
            RouteMarginRowOut(
                ruta=str(b["display"]),
                total_portes=n,
                ingresos_totales=ing,
                costes_totales=cst,
                margen_neto=margen,
                margen_porcentual=pct,
            )
        )

    out.sort(key=lambda r: r.margen_neto, reverse=True)
    return out[:10]


@router.get(
    "/credit-alerts",
    response_model=list[CreditAlertOut],
    summary="Alertas de límite de crédito (consumo ≥ 80 %)",
)
async def credit_limit_alerts(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> list[CreditAlertOut]:
    empresa_id = str(current_user.empresa_id)
    pending_by_client, _, _ = await aggregate_pending_and_trend(db, empresa_id, months_for_trend=None)

    res_clientes: Any = await db.execute(
        filter_not_deleted(
            db.table("clientes")
            .select("id, nombre, limite_credito")
            .eq("empresa_id", empresa_id)
        )
    )
    rows = (res_clientes.data or []) if hasattr(res_clientes, "data") else []

    out: list[CreditAlertOut] = []
    for row in rows:
        cid = str(row.get("id") or "").strip()
        if not cid:
            continue
        saldo = round(max(0.0, _to_float(pending_by_client.get(cid, 0.0))), 2)
        limite_credito = max(0.0, _to_float(row.get("limite_credito")))

        pct_raw = _porcentaje_consumo_limite(saldo_pendiente=saldo, limite_credito=limite_credito)
        porcentaje_consumo = round(pct_raw, 2)

        if porcentaje_consumo < 80.0:
            continue

        nivel_alerta = "CRITICAL" if porcentaje_consumo >= 100.0 else "WARNING"
        out.append(
            CreditAlertOut(
                cliente_id=cid,
                nombre_cliente=str(row.get("nombre") or "").strip() or "(sin nombre)",
                saldo_pendiente=saldo,
                limite_credito=round(limite_credito, 2),
                porcentaje_consumo=porcentaje_consumo,
                nivel_alerta=nivel_alerta,
            )
        )

    out.sort(key=lambda a: a.porcentaje_consumo, reverse=True)
    return out


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
    pending_by_client, trend_raw, use_portes_fallback = await aggregate_pending_and_trend(
        db, empresa_id, months_for_trend=months
    )

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

    mix = await _flota_counts_normativa_euro(db=db, empresa_id=empresa_id)
    esg_metodologia = _esg_texto_metodologia_certificado(counts=mix)

    return {
        "periodo": period,
        "total_co2_kg": round(total, 6),
        "total_portes": len(rows),
        "total_km": round(total_km, 3),
        "empresa_nombre": empresa_nombre,
        "esg_metodologia": esg_metodologia,
        "flota_normativa_counts": mix,
    }


@router.get(
    "/esg-report/download",
    summary="Descargar certificado ESG mensual en PDF",
)
async def monthly_esg_report_download(
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> StreamingResponse:
    report_data = await _build_esg_monthly_report_data(
        db=db,
        empresa_id=str(current_user.empresa_id),
    )
    pdf_bytes = generate_esg_certificate(report_data)
    period = str(report_data.get("periodo") or date.today().strftime("%Y-%m"))
    dispatch_webhook(
        empresa_id=str(current_user.empresa_id),
        event_type=WebhookEventType.ESG_CERTIFICATE_GENERATED.value,
        payload={
            "periodo": period,
            "total_co2_kg": float(report_data.get("total_co2_kg") or 0.0),
            "total_portes": int(report_data.get("total_portes") or 0),
        },
        background_tasks=background_tasks,
    )
    filename = f"certificado_esg_{period}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
