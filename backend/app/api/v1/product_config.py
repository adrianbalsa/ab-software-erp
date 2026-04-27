from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.constants import COSTE_OPERATIVO_EUR_KM
from app.schemas.product_config import OperationalPricingOut
from app.schemas.usage import MonthlyUsageOut
from app.schemas.user import UserOut
from app.services.usage_quota_service import UsageQuotaService

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/operational-pricing", response_model=OperationalPricingOut)
async def operational_pricing(
    _: UserOut = Depends(deps.get_current_active_user),
) -> OperationalPricingOut:
    """Devuelve el coste operativo €/km activo (misma fuente que mapas / BI / IA)."""
    return OperationalPricingOut(coste_operativo_eur_km=float(COSTE_OPERATIVO_EUR_KM))


@router.get("/cost-usage", response_model=MonthlyUsageOut)
async def cost_usage(
    current_user: UserOut = Depends(deps.get_current_active_user),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
) -> MonthlyUsageOut:
    """Consulta el consumo mensual frente a hard caps de Maps/OCR/IA del tenant."""
    return await quotas.current_usage(empresa_id=str(current_user.empresa_id))
