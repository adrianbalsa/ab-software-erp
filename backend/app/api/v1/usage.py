from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.usage import MonthlyUsageOut
from app.schemas.user import UserOut
from app.services.usage_quota_service import UsageQuotaService

router = APIRouter(tags=["Uso y cuotas"])


@router.get("/usage", response_model=MonthlyUsageOut)
async def usage(
    current_user: UserOut = Depends(deps.get_current_active_user),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
) -> MonthlyUsageOut:
    """Consumo mensual del tenant frente a cuotas de Maps/OCR/IA por plan."""
    return await quotas.current_usage(empresa_id=str(current_user.empresa_id))
