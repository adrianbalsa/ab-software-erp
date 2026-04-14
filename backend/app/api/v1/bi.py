"""
Business Intelligence (BI) — agregados listos para Recharts.

Acceso: rol operativo **owner** o rol legado de panel **admin** (`profiles.rol` / `UserOut.rol`).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import deps
from app.schemas.bi import BiDashboardSummaryOut, BiEsgImpactChartsOut, BiProfitabilityChartsOut
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


async def require_bi_owner_or_admin(
    current_user: UserOut = Depends(deps.get_current_user),
) -> UserOut:
    if current_user.rbac_role == "owner":
        return current_user
    if str(current_user.rol or "").strip().lower() == "admin":
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permiso denegado: se requiere rol owner o admin.",
    )


@router.get(
    "/dashboard/summary",
    response_model=BiDashboardSummaryOut,
    summary="KPIs de dashboard BI",
)
async def bi_dashboard_summary(
    current_user: UserOut = Depends(require_bi_owner_or_admin),
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
    current_user: UserOut = Depends(require_bi_owner_or_admin),
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
    current_user: UserOut = Depends(require_bi_owner_or_admin),
    service: BiService = Depends(deps.get_bi_service),
    date_range: tuple[date | None, date | None] = Depends(_bi_range_from_query),
) -> BiEsgImpactChartsOut:
    df, dt = date_range
    return await service.esg_impact_charts(empresa_id=str(current_user.empresa_id), date_from=df, date_to=dt)
