from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.constants import COSTE_OPERATIVO_EUR_KM
from app.schemas.product_config import OperationalPricingOut
from app.schemas.user import UserOut

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/operational-pricing", response_model=OperationalPricingOut)
async def operational_pricing(
    _: UserOut = Depends(deps.get_current_active_user),
) -> OperationalPricingOut:
    """Devuelve el coste operativo €/km activo (misma fuente que mapas / BI / IA)."""
    return OperationalPricingOut(coste_operativo_eur_km=float(COSTE_OPERATIVO_EUR_KM))
