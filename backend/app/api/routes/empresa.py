from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.plans import fetch_empresa_plan, max_vehiculos
from app.db.supabase import SupabaseAsync
from app.schemas.empresa import EmpresaQuotaOut
from app.schemas.user import UserOut
from app.services.flota_service import FlotaService

router = APIRouter()


@router.get("/quota", response_model=EmpresaQuotaOut)
async def get_quota(
    current_user: UserOut = Depends(deps.get_current_user),
    db: SupabaseAsync = Depends(deps.get_db),
) -> EmpresaQuotaOut:
    eid = str(current_user.empresa_id)
    plan = await fetch_empresa_plan(db, empresa_id=eid)
    limit = max_vehiculos(plan)
    fs = FlotaService(db)
    m = await fs.metricas_flota(empresa_id=eid)
    return EmpresaQuotaOut(
        plan_type=plan,
        limite_vehiculos=limit,
        vehiculos_actuales=m.total_vehiculos,
    )
