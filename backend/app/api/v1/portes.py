"""Rutas API v1 para portes (CMR, entrega POD, albarán).

El cálculo de márgenes en ``POST /portes/cotizar`` vive en ``app.api.routes.portes``;
allí se anulan ``margen_proyectado`` / ``precio_sugerido`` para ``traffic_manager``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.cmr import CmrDataOut
from app.schemas.porte import FirmaEntregaIn, FirmaEntregaOut
from app.schemas.user import UserOut
from app.services.portes_service import PortesService

router = APIRouter()


@router.get(
    "/{porte_id}/cmr-data",
    response_model=CmrDataOut,
    summary="Datos CMR para documentación de transporte",
)
async def get_porte_cmr_data(
    porte_id: UUID,
    current_user: UserOut = Depends(deps.get_current_user),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="portes", path_param="porte_id")
    ),
    service: PortesService = Depends(deps.get_portes_service),
) -> CmrDataOut:
    """
    Datos agregados para Carta de Porte (CMR). Misma visibilidad que ``GET /portes/{id}`` (RLS / tenant).
    """
    row = await service.get_cmr_data(empresa_id=current_user.empresa_id, porte_id=porte_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Porte no encontrado")
    return row


@router.post(
    "/{porte_id}/firmar-entrega",
    response_model=FirmaEntregaOut,
    summary="Firmar entrega y cerrar porte",
)
async def firmar_entrega(
    porte_id: UUID,
    body: FirmaEntregaIn,
    current_user: UserOut = Depends(deps.bind_write_context),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="portes", path_param="porte_id")
    ),
    service: PortesService = Depends(deps.get_portes_service),
) -> FirmaEntregaOut:
    """
    Registra firma del consignatario y marca el porte como **Entregado**.
    Conductores: vehículo del porte = assigned_vehiculo_id o conductor_asignado_id = perfil.
    """
    try:
        out = await service.firmar_entrega(
            empresa_id=current_user.empresa_id,
            porte_id=porte_id,
            current_user=current_user,
            firma_b64=body.firma_b64,
            nombre_consignatario=body.nombre_consignatario,
            dni_consignatario=body.dni_consignatario,
        )
        return FirmaEntregaOut(
            porte_id=UUID(str(out["porte_id"])),
            estado=str(out["estado"]),
            fecha_entrega_real=out["fecha_entrega_real"],
            odometro_actualizado=bool(out.get("odometro_actualizado", False)),
            odometro_error=str(out["odometro_error"]) if out.get("odometro_error") else None,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        msg = str(e)
        if "no encontrado" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e


@router.get(
    "/{porte_id}/albaran-entrega",
    summary="Descargar PDF de albarán de entrega",
)
async def descargar_albaran_entrega(
    porte_id: UUID,
    current_user: UserOut = Depends(deps.get_current_user),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="portes", path_param="porte_id")
    ),
    service: PortesService = Depends(deps.get_portes_service),
) -> StreamingResponse:
    """PDF albarán con firma incrustada (tras entrega confirmada)."""
    try:
        pdf_bytes = await service.get_albaran_entrega_pdf(
            empresa_id=current_user.empresa_id,
            porte_id=porte_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    fname = f"albaran_entrega_{porte_id}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
