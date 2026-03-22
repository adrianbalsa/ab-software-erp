from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
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
    return await service.stats(empresa_id=current_user.empresa_id)

