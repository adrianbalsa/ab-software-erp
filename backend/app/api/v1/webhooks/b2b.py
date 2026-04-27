"""Gestión de webhooks B2B (suscripciones por evento) y endpoints multi-evento con HMAC."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from starlette.responses import Response

from app.api import deps
from app.core.webhook_dispatcher import dispatch_endpoint_test
from app.schemas.user import UserOut
from app.schemas.webhook_b2b import (
    WebhookB2BCreated,
    WebhookB2BCreate,
    WebhookB2BOut,
    WebhookB2BSecretOut,
    WebhookTestOut,
)
from app.schemas.webhook_endpoint import (
    WebhookEndpointCreate,
    WebhookEndpointCreated,
    WebhookEndpointOut,
    WebhookEndpointSecretOut,
    WebhookEndpointTestOut,
    WebhookEndpointUpdate,
    WebhookEventCatalogOut,
)
from app.services.webhook_endpoints_service import WebhookEndpointsService
from app.services.webhook_service import dispatch_webhook_test
from app.services.webhooks_admin_service import WebhooksAdminService

router = APIRouter()

_owner_or_developer = deps.require_role("owner", "developer")
_owner_or_developer_write = deps.require_write_role("owner", "developer")


@router.get(
    "/",
    response_model=list[WebhookB2BOut],
    summary="Listar webhooks B2B activos",
)
async def list_webhooks(
    current_user: UserOut = Depends(deps.require_role("owner")),
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
    current_user: UserOut = Depends(deps.require_write_role("owner")),
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
    current_user: UserOut = Depends(deps.require_role("owner")),
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
    current_user: UserOut = Depends(deps.require_write_role("owner")),
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
    current_user: UserOut = Depends(deps.require_write_role("owner")),
    service: WebhooksAdminService = Depends(deps.get_webhooks_admin_service),
) -> Response:
    """Desactiva la suscripción (no borra el historial de logs)."""
    await service.deactivate(empresa_id=current_user.empresa_id, webhook_id=webhook_id)
    return Response(status_code=204)


# --- Endpoints multi-evento (cabecera X-ABLogistics-Signature) ---


@router.get(
    "/endpoints/events",
    response_model=WebhookEventCatalogOut,
    summary="Catálogo de eventos webhook",
)
async def list_webhook_event_catalog(
    _: UserOut = Depends(_owner_or_developer),
) -> WebhookEventCatalogOut:
    return WebhookEventCatalogOut()


@router.get(
    "/endpoints",
    response_model=list[WebhookEndpointOut],
    summary="Listar endpoints de webhook (multi-evento)",
)
async def list_webhook_endpoints(
    current_user: UserOut = Depends(_owner_or_developer),
    service: WebhookEndpointsService = Depends(deps.get_webhook_endpoints_service),
) -> list[WebhookEndpointOut]:
    return await service.list_all(empresa_id=current_user.empresa_id)


@router.post(
    "/endpoints",
    response_model=WebhookEndpointCreated,
    summary="Crear endpoint de webhook (multi-evento)",
)
async def create_webhook_endpoint(
    body: WebhookEndpointCreate,
    current_user: UserOut = Depends(_owner_or_developer_write),
    service: WebhookEndpointsService = Depends(deps.get_webhook_endpoints_service),
) -> WebhookEndpointCreated:
    return await service.create(empresa_id=current_user.empresa_id, payload=body)


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointOut,
    summary="Obtener endpoint de webhook",
)
async def get_webhook_endpoint(
    endpoint_id: UUID,
    current_user: UserOut = Depends(_owner_or_developer),
    service: WebhookEndpointsService = Depends(deps.get_webhook_endpoints_service),
) -> WebhookEndpointOut:
    return await service.get_one(empresa_id=current_user.empresa_id, endpoint_id=endpoint_id)


@router.put(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointOut,
    summary="Actualizar endpoint de webhook",
)
async def update_webhook_endpoint(
    endpoint_id: UUID,
    body: WebhookEndpointUpdate,
    current_user: UserOut = Depends(_owner_or_developer_write),
    service: WebhookEndpointsService = Depends(deps.get_webhook_endpoints_service),
) -> WebhookEndpointOut:
    return await service.update(empresa_id=current_user.empresa_id, endpoint_id=endpoint_id, payload=body)


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=204,
    summary="Desactivar endpoint de webhook",
)
async def delete_webhook_endpoint(
    endpoint_id: UUID,
    current_user: UserOut = Depends(_owner_or_developer_write),
    service: WebhookEndpointsService = Depends(deps.get_webhook_endpoints_service),
) -> Response:
    await service.deactivate(empresa_id=current_user.empresa_id, endpoint_id=endpoint_id)
    return Response(status_code=204)


@router.get(
    "/endpoints/{endpoint_id}/secret",
    response_model=WebhookEndpointSecretOut,
    summary="Obtener secreto HMAC del endpoint",
)
async def get_webhook_endpoint_secret(
    endpoint_id: UUID,
    current_user: UserOut = Depends(_owner_or_developer),
    service: WebhookEndpointsService = Depends(deps.get_webhook_endpoints_service),
) -> WebhookEndpointSecretOut:
    return await service.get_secret(empresa_id=current_user.empresa_id, endpoint_id=endpoint_id)


@router.post(
    "/endpoints/{endpoint_id}/test",
    response_model=WebhookEndpointTestOut,
    summary="Enviar prueba firmada (X-ABLogistics-Signature)",
)
async def test_webhook_endpoint(
    endpoint_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(_owner_or_developer_write),
) -> WebhookEndpointTestOut:
    dispatch_endpoint_test(
        empresa_id=str(current_user.empresa_id),
        endpoint_id=str(endpoint_id),
        background_tasks=background_tasks,
    )
    return WebhookEndpointTestOut(status="queued")
