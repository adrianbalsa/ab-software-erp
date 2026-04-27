from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import deps
from app.models.enums import UserRole
from app.schemas.bi import ProfitMarginAnalyticsOut
from app.schemas.finance import SimulationInput, SimulationResultOut
from app.schemas.geo_activity import GeoActivityResponse
from app.schemas.user import UserOut
from app.services.bi_service import BiService
from app.services.geo_activity_service import GeoActivityService
from app.services.simulation_service import SimulationService
from app.db.supabase import SupabaseAsync

router = APIRouter()


@router.get(
    "/analytics/geo-activity",
    response_model=GeoActivityResponse,
    summary="Geostamps de portes (portal, tenant o admin) para mapas",
)
async def geo_activity(
    current_user: UserOut = Depends(deps.get_current_user),
    service: GeoActivityService = Depends(deps.get_geo_activity_service),
) -> GeoActivityResponse:
    """
    Coordenadas persistidas en ``portes`` (Fase 4: geocodificación origen/destino).

    - **Portal cliente** (``role=cliente``): últimas entregas del cargador (solo destino / entrega).
    - **Tenant** (admin/gestor de empresa): puntos recogida+entrega y capa ``heatmap`` agregada.
    - **Plataforma** (``superadmin``/``developer``): heatmap global (sujeto a RLS / políticas Supabase).

    ``margen_operativo`` ≈ precio pactado menos suma de ``gastos.total_eur`` con ``porte_id``; oculto para ``traffic_manager``.
    """
    allowed = {
        UserRole.CLIENTE,
        UserRole.ADMIN,
        UserRole.GESTOR,
        UserRole.SUPERADMIN,
        UserRole.DEVELOPER,
    }
    if current_user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para analytics geo-activity",
        )
    try:
        return await service.load_for_user(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/analytics/simulate",
    response_model=SimulationResultOut,
    summary="Simulador de impacto económico (3 meses)",
)
async def simulate_impact(
    payload: SimulationInput,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> SimulationResultOut:
    service = SimulationService(db)
    return await service.calcular_simulacion(
        empresa_id=str(current_user.empresa_id),
        params=payload,
    )


def _margin_range_from_query(
    range_from: Annotated[
        date | None,
        Query(alias="from", description="Inicio (YYYY-MM-DD), inclusive."),
    ] = None,
    range_to: Annotated[
        date | None,
        Query(alias="to", description="Fin (YYYY-MM-DD), inclusive."),
    ] = None,
) -> tuple[date | None, date | None]:
    if range_from is not None and range_to is not None and range_from > range_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El parámetro from no puede ser posterior a to.",
        )
    return range_from, range_to


@router.get(
    "/analytics/profit-margin",
    response_model=ProfitMarginAnalyticsOut,
    summary="Serie agregada de ingresos, gastos y margen (HALF_EVEN)",
)
async def analytics_profit_margin(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: BiService = Depends(deps.get_bi_service),
    date_range: tuple[date | None, date | None] = Depends(_margin_range_from_query),
    granularity: Annotated[Literal["month", "week"], Query(description="Agrupación temporal.")] = "month",
    vehiculo_id: Annotated[UUID | None, Query(description="Filtrar portes/gastos vinculados por vehículo.")] = None,
    cliente_id: Annotated[UUID | None, Query(description="Filtrar por cliente del porte.")] = None,
) -> ProfitMarginAnalyticsOut:
    df, dt = date_range
    return await service.profit_margin_analytics(
        empresa_id=str(current_user.empresa_id),
        date_from=df,
        date_to=dt,
        granularity=granularity,
        vehiculo_id=str(vehiculo_id) if vehiculo_id else None,
        cliente_id=str(cliente_id) if cliente_id else None,
    )
