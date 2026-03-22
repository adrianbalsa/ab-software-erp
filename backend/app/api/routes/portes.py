from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.schemas.factura import FacturaCreateFromPortes, FacturaGenerateResult
from app.schemas.porte import PorteCreate, PorteOut
from app.schemas.user import UserOut
from app.services.facturas_service import FacturasService
from app.services.portes_service import PortesService


router = APIRouter()


@router.get("/", response_model=list[PorteOut])
async def list_portes(
    current_user: UserOut = Depends(deps.get_current_user),
    service: PortesService = Depends(deps.get_portes_service),
) -> list[PorteOut]:
    return await service.list_portes_pendientes(empresa_id=current_user.empresa_id)


@router.post("/", response_model=PorteOut, status_code=status.HTTP_201_CREATED)
async def create_porte(
    porte_in: PorteCreate,
    current_user: UserOut = Depends(deps.bind_write_context),
    service: PortesService = Depends(deps.get_portes_service),
) -> PorteOut:
    try:
        return await service.create_porte(empresa_id=current_user.empresa_id, porte_in=porte_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/facturar",
    response_model=FacturaGenerateResult,
    status_code=status.HTTP_201_CREATED,
)
async def facturar_desde_portes(
    payload: FacturaCreateFromPortes,
    current_user: UserOut = Depends(deps.bind_write_context),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaGenerateResult:
    """
    Factura legal (InvoicePDF + VeriFactu encadenado) vía `FacturasService`
    → `verifactu_service` + `integrations/pdf_adapter` → `pdf_service`.
    """
    return await facturas.generar_desde_portes(
        empresa_id=current_user.empresa_id,
        payload=payload,
        usuario_id=current_user.usuario_id or current_user.username,
    )


@router.get("/{porte_id}", response_model=PorteOut)
async def get_porte(
    porte_id: UUID,
    current_user: UserOut = Depends(deps.get_current_user),
    service: PortesService = Depends(deps.get_portes_service),
) -> PorteOut:
    """
    Detalle de un porte **solo si pertenece al tenant** del JWT (misma semántica que RLS por ``empresa_id``).
    """
    row = await service.get_porte(empresa_id=current_user.empresa_id, porte_id=porte_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Porte no encontrado")
    return row

