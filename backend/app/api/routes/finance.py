from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.finance import FinanceDashboardOut, FinanceSummaryOut
from app.schemas.user import UserOut
from app.services.finance_service import FinanceService


router = APIRouter()


@router.get("/summary", response_model=FinanceSummaryOut)
async def finance_summary(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: FinanceService = Depends(deps.get_finance_service),
) -> FinanceSummaryOut:
    """
    EBITDA operativo (aprox.) e ingresos/gastos **netos de IVA** por empresa.

    Delega en `FinanceService.financial_summary` (consultas vía SupabaseAsync).
    """
    return await service.financial_summary(empresa_id=current_user.empresa_id)


@router.get("/dashboard", response_model=FinanceDashboardOut)
async def finance_dashboard(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: FinanceService = Depends(deps.get_finance_service),
) -> FinanceDashboardOut:
    """
    KPIs financieros, ``margen_km_eur`` (EBITDA / km snapshot facturado) y comparativa 6 meses.
    """
    return await service.financial_dashboard(empresa_id=current_user.empresa_id)
