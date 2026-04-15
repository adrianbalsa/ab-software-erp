"""
Dashboard económico avanzado (Math Engine) — solo rol **owner** (RBAC).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.economic_insights import AdvancedMetricsOut, EconomicInsightsOut
from app.schemas.treasury import TreasuryProjectionOut
from app.schemas.user import UserOut
from app.services.finance_service import FinanceService
from app.services.treasury_service import TreasuryService

router = APIRouter()


@router.get(
    "/advanced-metrics",
    response_model=AdvancedMetricsOut,
    summary="Métricas avanzadas (6 meses)",
)
async def advanced_metrics(
    current_user: UserOut = Depends(deps.get_current_user),
    _: None = Depends(deps.RoleChecker(["admin", "gestor"])),
    service: FinanceService = Depends(deps.get_finance_service),
) -> AdvancedMetricsOut:
    """
    KPIs últimos 6 meses: margen contribución (facturación − gastos), coste por km operativo,
    CO₂ y ratio ingresos/CO₂ (EBITDA verde). Agregados vía Supabase (RLS empresa).
    """
    return await service.advanced_metrics_last_six_months(empresa_id=str(current_user.empresa_id))


@router.get(
    "/economic-insights",
    response_model=EconomicInsightsOut,
    summary="Insights económicos avanzados",
)
async def economic_insights(
    current_user: UserOut = Depends(deps.get_current_user),
    _: None = Depends(deps.RoleChecker(["admin"])),
    service: FinanceService = Depends(deps.get_finance_service),
) -> EconomicInsightsOut:
    """
    Agregados operativos (sin IVA) para visualización avanzada: coste/km (30d),
    ranking de clientes, series 12 meses, punto de equilibrio y margen/km vs combustible/km.

    No expone campos cifrados en reposo; solo totales ya desencriptados por PostgREST según RLS.
    """
    return await service.economic_insights_advanced(empresa_id=str(current_user.empresa_id))


@router.get(
    "/treasury-projection",
    response_model=TreasuryProjectionOut,
    summary="Proyección de cobros y PMC (tesorería)",
)
async def treasury_projection(
    current_user: UserOut = Depends(deps.require_role("owner")),
    treasury: TreasuryService = Depends(deps.get_treasury_service),
) -> TreasuryProjectionOut:
    """
    Cuentas por cobrar pendientes agrupadas por fecha estimada de cobro (cubos) y
    periodo medio de cobro (PMC) sobre facturas ya cobradas, con tendencia 90d vs 90d previos.
    """
    return await treasury.treasury_projection(empresa_id=str(current_user.empresa_id))
