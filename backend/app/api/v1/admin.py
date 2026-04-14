"""Rutas de administración del tenant bajo ``/api/v1/admin``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.schemas.audit_log import AuditLogOut
from app.schemas.user import UserOut
from app.services.audit_logs_service import AuditLogsService

router = APIRouter()


@router.get(
    "/audit-logs",
    response_model=list[AuditLogOut],
    summary="Historial de auditoría (triggers + eventos API)",
)
async def list_admin_audit_logs(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: AuditLogsService = Depends(deps.get_audit_logs_service),
    limit: int = Query(default=200, ge=1, le=500),
    table_name: str | None = Query(default=None, max_length=128),
    record_id: str | None = Query(default=None, max_length=128),
) -> list[AuditLogOut]:
    """
    Línea temporal de cambios en tablas auditadas (``facturas``, ``portes``, ``bank_transactions``, …).
    Con ``record_id`` los resultados van en orden cronológico ascendente; sin él, del más reciente al más antiguo.
    """
    rid = str(record_id).strip() if record_id else None
    ascending = bool(rid)
    return await service.list_for_empresa(
        empresa_id=str(current_user.empresa_id),
        limit=limit,
        table_name=str(table_name).strip() if table_name else None,
        record_id=rid,
        ascending=ascending,
    )
