from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api import deps
from app.schemas.cliente import ClienteCreate, ClienteOut
from app.schemas.user import UserOut
from app.services.clientes_service import ClientesService

router = APIRouter()


@router.get("/", response_model=list[ClienteOut])
async def list_clientes(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: ClientesService = Depends(deps.get_clientes_service),
) -> list[ClienteOut]:
    return await service.list_clientes(empresa_id=current_user.empresa_id)


@router.post("/", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
async def create_cliente(
    payload: ClienteCreate,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: ClientesService = Depends(deps.get_clientes_service),
) -> ClienteOut:
    try:
        return await service.create_cliente(empresa_id=current_user.empresa_id, payload=payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{cliente_id}", response_model=ClienteOut)
async def get_cliente(
    cliente_id: UUID,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: ClientesService = Depends(deps.get_clientes_service),
) -> ClienteOut:
    row = await service.get_cliente(empresa_id=current_user.empresa_id, cliente_id=cliente_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return row


@router.delete(
    "/{cliente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_cliente(
    cliente_id: UUID,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: ClientesService = Depends(deps.get_clientes_service),
) -> Response:
    await service.soft_delete_cliente(empresa_id=current_user.empresa_id, cliente_id=cliente_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
