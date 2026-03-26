from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.esg_audit import ESGAuditOut
from app.schemas.user import UserOut
from app.services.esg_audit_service import EsgAuditService

router = APIRouter(prefix="/esg")


async def get_esg_audit_service(db: SupabaseAsync = Depends(deps.get_db)) -> EsgAuditService:
    return EsgAuditService(db)


@router.get(
    "/audit-report",
    response_model=ESGAuditOut,
    summary="Informe de auditoría ESG del periodo",
)
async def esg_audit_report(
    fecha_inicio: date = Query(..., description="Inicio del periodo (inclusive)"),
    fecha_fin: date = Query(..., description="Fin del periodo (inclusive)"),
    escenario_optimizacion_pct: float = Query(
        25.0,
        ge=0,
        le=100,
        description="% de portes Euro V considerados en el escenario de ahorro (vs Euro VI)",
    ),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: EsgAuditService = Depends(get_esg_audit_service),
) -> ESGAuditOut:
    """
    Informe de auditoría ESG: huella total, top clientes, desglose por certificación de flota
    e insight de optimización (escenario Euro V → Euro VI).
    """
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual que fecha_inicio.",
        )
    return await service.audit_report(
        empresa_id=str(current_user.empresa_id),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        escenario_pct=escenario_optimizacion_pct,
    )
