from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.finance import SimulationInput, SimulationResultOut
from app.schemas.user import UserOut
from app.services.simulation_service import SimulationService
from app.db.supabase import SupabaseAsync

router = APIRouter()


@router.post(
    "/analytics/simulate",
    response_model=SimulationResultOut,
    summary="Simulador de impacto económico (3 meses)",
)
async def simulate_impact(
    payload: SimulationInput,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> SimulationResultOut:
    service = SimulationService(db)
    return await service.calcular_simulacion(
        empresa_id=str(current_user.empresa_id),
        params=payload,
    )
