"""Conciliación bancaria asistida por IA (movimientos_bancarios ↔ facturas)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import Response

from app.api import deps
from app.schemas.conciliacion import (
    ConciliarAiOut,
    ConfirmarSugerenciaIn,
    MovimientoSugeridoOut,
)
from app.schemas.user import UserOut
from app.services.reconciliation_service import ReconciliationService

router = APIRouter()


@router.post(
    "/conciliar-ai",
    response_model=ConciliarAiOut,
    summary="Conciliación bancaria asistida por IA",
)
async def conciliar_con_ia(
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner")),
    service: ReconciliationService = Depends(deps.get_reconciliation_service),
) -> ConciliarAiOut:
    """
    Genera sugerencias con LLM y las persiste (movimiento → Sugerido + factura_id).
    Si el JSON del modelo es inválido o los IDs no existen, no se modifica la base de datos.
    """
    try:
        return await service.ejecutar_conciliacion_ia_completa(empresa_id=str(current_user.empresa_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/sugerencias-pendientes",
    response_model=list[MovimientoSugeridoOut],
    summary="Listar sugerencias de conciliación pendientes",
)
async def listar_sugerencias_pendientes(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: ReconciliationService = Depends(deps.get_reconciliation_service),
) -> list[MovimientoSugeridoOut]:
    """Movimientos en estado Sugerido para revisión en la UI."""
    rows = await service.listar_movimientos_sugeridos(empresa_id=str(current_user.empresa_id))
    return [MovimientoSugeridoOut(**r) for r in rows]


@router.post(
    "/confirmar-sugerencia",
    summary="Confirmar o rechazar sugerencia de conciliación",
)
async def confirmar_sugerencia(
    body: ConfirmarSugerenciaIn,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner")),
    service: ReconciliationService = Depends(deps.get_reconciliation_service),
) -> Response:
    """
    Aprueba (Conciliado + factura cobrada) o rechaza (vuelve a Pendiente) una sugerencia.
    """
    try:
        await service.confirmar_sugerencia(
            empresa_id=str(current_user.empresa_id),
            movimiento_id=body.movimiento_id,
            aprobar=body.aprobar,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
