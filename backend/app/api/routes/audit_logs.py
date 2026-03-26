from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.schemas.audit_log import AuditLogOut
from app.schemas.user import UserOut
from app.services.audit_logs_service import AuditLogsService
from app.db.supabase import SupabaseAsync

router = APIRouter()


async def _get_audit_logs_service(db: SupabaseAsync = Depends(deps.get_db)) -> AuditLogsService:
    return AuditLogsService(db)


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: AuditLogsService = Depends(_get_audit_logs_service),
    limit: int = Query(default=100, ge=1, le=500),
    table_name: str | None = Query(default=None, max_length=128),
) -> list[AuditLogOut]:
    """
    Historial de auditoría del tenant (tablas portes, facturas, gastos).
    Solo **owner**; filtrado por ``empresa_id`` del JWT / sesión RLS.
    """
    return await service.list_for_empresa(
        empresa_id=str(current_user.empresa_id),
        limit=limit,
        table_name=table_name,
    )
