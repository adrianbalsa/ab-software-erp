"""Gestión de webhooks B2B (suscripciones por empresa)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from starlette.responses import Response

from app.api import deps
from app.core.rbac import RoleChecker
from app.schemas.user import UserOut
from app.schemas.webhook_b2b import (
    WebhookB2BCreated,
    WebhookB2BCreate,
    WebhookB2BOut,
    WebhookB2BSecretOut,
    WebhookTestOut,
)
from app.services.webhook_service import dispatch_webhook_test
from app.services.webhooks_admin_service import WebhooksAdminService

router = APIRouter()


@router.get(
    "/",
    response_model=list[WebhookB2BOut],
    summary="Listar webhooks B2B activos",
)
async def list_webhooks(
    _: dict[str, Any] = Depends(RoleChecker(["ADMIN"])),
    current_user: UserOut = Depends(deps.get_current_user),
    service: WebhooksAdminService = Depends(deps.get_webhooks_admin_service),
) -> list[WebhookB2BOut]:
    """Lista suscripciones activas de la empresa del token."""
    return await service.list_active(empresa_id=current_user.empresa_id)


@router.post(
    "/",
    response_model=WebhookB2BCreated,
    summary="Crear suscripción webhook",
)
async def create_webhook(
    body: WebhookB2BCreate,
    _: dict[str, Any] = Depends(RoleChecker(["ADMIN"])),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: WebhooksAdminService = Depends(deps.get_webhooks_admin_service),
) -> WebhookB2BCreated:
    """Crea un webhook (HTTPS obligatorio); devuelve `secret_key` solo en esta respuesta."""
    return await service.create(empresa_id=current_user.empresa_id, payload=body)


@router.get(
    "/{webhook_id}/secret",
    response_model=WebhookB2BSecretOut,
    summary="Obtener secreto HMAC del webhook",
)
async def get_webhook_secret(
    webhook_id: UUID,
    _: dict[str, Any] = Depends(RoleChecker(["ADMIN"])),
    current_user: UserOut = Depends(deps.get_current_user),
    service: WebhooksAdminService = Depends(deps.get_webhooks_admin_service),
) -> WebhookB2BSecretOut:
    """Revela el secreto HMAC para una suscripción activa."""
    return await service.get_secret(empresa_id=current_user.empresa_id, webhook_id=webhook_id)


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestOut,
    summary="Enviar evento de prueba firmado",
)
async def test_webhook(
    webhook_id: UUID,
    background_tasks: BackgroundTasks,
    _: dict[str, Any] = Depends(RoleChecker(["ADMIN"])),
    current_user: UserOut = Depends(deps.bind_write_context),
) -> WebhookTestOut:
    """Encola un POST de prueba (ping) firmado hacia la URL configurada."""
    dispatch_webhook_test(
        empresa_id=str(current_user.empresa_id),
        webhook_id=str(webhook_id),
        background_tasks=background_tasks,
    )
    return WebhookTestOut(status="queued")


@router.delete(
    "/{webhook_id}",
    status_code=204,
    summary="Desactivar webhook",
)
async def delete_webhook(
    webhook_id: UUID,
    _: dict[str, Any] = Depends(RoleChecker(["ADMIN"])),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: WebhooksAdminService = Depends(deps.get_webhooks_admin_service),
) -> Response:
    """Desactiva la suscripción (no borra el historial de logs)."""
    await service.deactivate(empresa_id=current_user.empresa_id, webhook_id=webhook_id)
    return Response(status_code=204)
