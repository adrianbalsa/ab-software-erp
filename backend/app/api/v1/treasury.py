"""Tesorería y agregados de liquidez (fiat)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.treasury import CashFlowOut
from app.schemas.user import UserOut
from app.services.treasury_service import TreasuryService

router = APIRouter()


@router.get(
    "/cash-flow",
    response_model=CashFlowOut,
    summary="Snapshot de tesorería y flujo de caja",
)
async def get_cash_flow(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: TreasuryService = Depends(deps.get_treasury_service),
) -> CashFlowOut:
    """
    Saldo estimado (movimientos conciliados), AR/AP y proyección 30 días.
    Importes redondeados con el motor fiat (round_fiat / as_float_fiat).
    """
    return await service.cash_flow_snapshot(empresa_id=str(current_user.empresa_id))
