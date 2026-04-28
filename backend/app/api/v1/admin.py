"""Rutas de administración del tenant bajo ``/api/v1/admin``."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.api import deps
from app.schemas.audit_log import AuditLogOut
from app.schemas.user import UserOut
from app.services.audit_logs_service import AuditLogsService
from app.services.notification_service import send_alert

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


@router.post(
    "/test-alert",
    summary="Smoke-test de alertas webhook",
    status_code=status.HTTP_202_ACCEPTED,
)
async def test_alert_webhook(
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.require_role("owner")),
) -> dict[str, str]:
    """
    Dispara una alerta de prueba para validar que ALERT_WEBHOOK_URL
    esta correctamente desplegada y enruta hacia el canal on-call.
    """
    tenant_id = str(current_user.empresa_id)
    ts = datetime.now(timezone.utc).isoformat()
    background_tasks.add_task(
        send_alert,
        "Smoke test: alerta operativa",
        (
            "Prueba manual post-despliegue del canal de alertas. "
            "No requiere accion correctiva."
        ),
        "INFO",
        {
            "tenant_id": tenant_id,
            "triggered_by": str(current_user.username),
            "smoke_test": True,
            "timestamp": ts,
            "source_endpoint": "/api/v1/admin/test-alert",
        },
    )
    return {"status": "queued", "detail": "Alert queued for asynchronous delivery"}
