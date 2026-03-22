from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.presupuesto import PresupuestoCalculoIn, PresupuestoCalculoOut
from app.schemas.user import UserOut
from app.services.presupuestos_service import PresupuestosService


router = APIRouter()


@router.post("/calcular", response_model=PresupuestoCalculoOut)
async def calcular_presupuesto(
    payload: PresupuestoCalculoIn,
    current_user: UserOut = Depends(deps.get_current_user),
    service: PresupuestosService = Depends(deps.get_presupuestos_service),
) -> PresupuestoCalculoOut:
    # Tenant desde JWT/cookie (ensure_empresa_context); nunca desde el body (anti-spoofing).
    _ = current_user.empresa_id
    return await service.calcular(payload=payload)
