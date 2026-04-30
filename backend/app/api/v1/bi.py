"""
Business Intelligence (BI) — agregados listos para Recharts.

Acceso: rol operativo **owner** (normalizado desde perfiles legacy admin en `deps.require_role`).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import deps
from app.schemas.bi import BiDashboardSummaryOut, BiEsgImpactChartsOut, BiProfitabilityChartsOut, FinancialHealthOut
from app.schemas.user import UserOut
from app.services.bi_service import BiService

router = APIRouter(prefix="/bi", tags=["Business Intelligence"])


def _bi_range_from_query(
    range_from: Annotated[
        date | None,
        Query(alias="from", description="Inicio del periodo (YYYY-MM-DD), inclusive."),
    ] = None,
    range_to: Annotated[
        date | None,
        Query(alias="to", description="Fin del periodo (YYYY-MM-DD), inclusive."),
    ] = None,
) -> tuple[date | None, date | None]:
    if range_from is not None and range_to is not None and range_from > range_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El parámetro from no puede ser posterior a to.",
        )
    return range_from, range_to


@router.get(
    "/dashboard/summary",
    response_model=BiDashboardSummaryOut,
    summary="KPIs de dashboard BI",
)
async def bi_dashboard_summary(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: BiService = Depends(deps.get_bi_service),
    date_range: tuple[date | None, date | None] = Depends(_bi_range_from_query),
) -> BiDashboardSummaryOut:
    df, dt = date_range
    return await service.dashboard_summary(empresa_id=str(current_user.empresa_id), date_from=df, date_to=dt)


@router.get(
    "/charts/profitability",
    response_model=BiProfitabilityChartsOut,
    summary="Scatter: km vs margen estimado",
)
async def bi_charts_profitability(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: BiService = Depends(deps.get_bi_service),
    date_range: tuple[date | None, date | None] = Depends(_bi_range_from_query),
) -> BiProfitabilityChartsOut:
    df, dt = date_range
    return await service.profitability_scatter(empresa_id=str(current_user.empresa_id), date_from=df, date_to=dt)


@router.get(
    "/charts/esg-impact",
    response_model=BiEsgImpactChartsOut,
    summary="Matriz ESG / EBITDA y datos para heatmap o treemap",
)
async def bi_charts_esg_impact(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: BiService = Depends(deps.get_bi_service),
    date_range: tuple[date | None, date | None] = Depends(_bi_range_from_query),
) -> BiEsgImpactChartsOut:
    df, dt = date_range
    return await service.esg_impact_charts(empresa_id=str(current_user.empresa_id), date_from=df, date_to=dt)


@router.get(
    "/financial-health",
    response_model=FinancialHealthOut,
    summary="Salud financiera (EBITDA, margen, cash flow y coste carbono)",
    description=(
        "Agregado financiero por período con series para Recharts. "
        "El coste de carbono se calcula con la fórmula: (CO2_kg / 1000) x precio ETS por tonelada."
    ),
)
async def bi_financial_health(
    start_date: date | None = Query(
        default=None,
        description="Fecha inicial ISO (YYYY-MM-DD). Por defecto: últimos 6 meses.",
    ),
    end_date: date | None = Query(
        default=None,
        description="Fecha final ISO (YYYY-MM-DD). Por defecto: hoy.",
    ),
    granularity: Literal["day", "week", "month"] = Query(
        default="month",
        description="Granularidad temporal de la serie: day, week o month.",
    ),
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: BiService = Depends(deps.get_bi_service),
) -> FinancialHealthOut:
    dt = end_date or date.today()
    df = start_date or (dt - timedelta(days=180))
    if df > dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date no puede ser posterior a end_date.",
        )
    return await service.get_company_financial_health(
        empresa_id=str(current_user.empresa_id),
        start_date=df,
        end_date=dt,
        granularity=granularity,
    )
