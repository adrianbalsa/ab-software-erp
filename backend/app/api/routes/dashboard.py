from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.core.rbac import VALID_ROLES
from app.schemas.dashboard import DashboardStatsOut
from app.schemas.user import UserOut
from app.services.dashboard_service import DashboardService
from app.db.supabase import SupabaseAsync


router = APIRouter()


async def _get_dashboard_service(db: SupabaseAsync = Depends(deps.get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/stats", response_model=DashboardStatsOut)
async def stats(
    current_user: UserOut = Depends(deps.get_current_user),
    service: DashboardService = Depends(_get_dashboard_service),
) -> DashboardStatsOut:
    role = (current_user.rbac_role or "").strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol no autorizado para estadísticas del dashboard.",
        )

    eid: str = str(current_user.empresa_id)

    if role == "owner":
        return await service.stats(empresa_id=eid)
    if role == "traffic_manager":
        return await service.stats_operativos_sin_finanzas(empresa_id=eid)
    if role == "driver":
        # Nunca agregado a nivel empresa; solo vehículo asignado o ceros (sin fuga de totales).
        if current_user.assigned_vehiculo_id is None:
            return DashboardStatsOut(
                ebitda_estimado=0.0,
                pendientes_cobro=0.0,
                km_totales_mes=0.0,
                bultos_mes=0,
            )
        return await service.stats_operativos_conductor(
            empresa_id=eid,
            vehiculo_id=str(current_user.assigned_vehiculo_id),
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Rol no contemplado para estadísticas del dashboard.",
    )

