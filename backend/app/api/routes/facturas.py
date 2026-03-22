from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api import deps
from app.schemas.factura import (
    FacturaCreateFromPortes,
    FacturaGenerateResult,
    FacturaOut,
    FacturaRectificarIn,
)
from app.schemas.user import UserOut
from app.services.email_service import send_invoice_email_from_base64
from app.services.facturas_service import FacturasService


router = APIRouter()


@router.get("/", response_model=list[FacturaOut])
async def list_facturas(
    current_user: UserOut = Depends(deps.get_current_user),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> list[FacturaOut]:
    return await service.list_facturas(empresa_id=current_user.empresa_id)


@router.post(
    "/desde-portes",
    response_model=FacturaGenerateResult,
    status_code=status.HTTP_201_CREATED,
)
async def generar_factura_desde_portes(
    payload: FacturaCreateFromPortes,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.bind_write_context),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaGenerateResult:
    try:
        result = await service.generar_desde_portes(
            empresa_id=current_user.empresa_id,
            payload=payload,
            usuario_id=current_user.usuario_id or current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Email (Resend) en segundo plano: solo si el cliente tiene email en `clientes.email` (ficha).
    cli = result.factura.cliente_detalle
    dest = (str(cli.email).strip() if cli and cli.email and str(cli.email).strip() else None)
    if dest and result.pdf_base64:
        f = result.factura
        factura_data: dict = {
            "numero_factura": f.numero_factura,
            "fecha_emision": f.fecha_emision.isoformat(),
            "total_factura": f.total_factura,
            "base_imponible": f.base_imponible,
            "cuota_iva": f.cuota_iva,
            "empresa_nombre": (f"Emisor fiscal {f.nif_emisor}" if f.nif_emisor else "AB Logistics OS"),
            "cliente_nombre": cli.nombre if cli else "Cliente",
        }
        background_tasks.add_task(
            send_invoice_email_from_base64,
            factura_data,
            result.pdf_base64,
            dest,
        )

    return result


@router.post(
    "/{factura_id}/rectificar",
    response_model=FacturaOut,
    status_code=status.HTTP_201_CREATED,
)
async def rectificar_factura(
    factura_id: int,
    payload: FacturaRectificarIn,
    current_user: UserOut = Depends(deps.bind_write_context),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaOut:
    """
    Emite R1 (importes negativos) sobre una F1 sellada; encadenamiento VeriFactu según especificación interna.
    """
    try:
        return await service.emitir_factura_rectificativa(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
            motivo=payload.motivo,
            usuario_id=current_user.usuario_id or current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

