from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api import deps
from app.core.rbac import RoleChecker
from app.schemas.factura import FacturaCreateFromPortes, FacturaGenerateResult
from app.schemas.porte import PorteCotizarIn, PorteCotizarOut, PorteCreate, PorteOut
from app.schemas.user import UserOut
from app.models.webhook import WebhookEventType
from app.services.facturas_service import FacturasService
from app.services.portes_service import PorteDomainError, PortesService
from app.services.webhook_service import dispatch_webhook


router = APIRouter()


def _redact_porte_for_driver(p: PorteOut, user: UserOut) -> PorteOut:
    if user.rbac_role != "driver":
        return p
    return p.model_copy(update={"precio_pactado": None, "cliente_id": None, "cliente_detalle": None})


def _mask_porte_cotizar_financials(out: PorteCotizarOut, user: UserOut) -> PorteCotizarOut:
    """Traffic manager: sin margen proyectado ni señales derivadas de rentabilidad."""
    if (user.rbac_role or "").strip().lower() != "traffic_manager":
        return out
    return out.model_copy(
        update={
            "margen_proyectado": None,
            "es_rentable": None,
            "precio_sugerido": None,
        }
    )


@router.get("/", response_model=list[PorteOut])
async def list_portes(
    current_user: UserOut = Depends(deps.get_current_user),
    service: PortesService = Depends(deps.get_portes_service),
) -> list[PorteOut]:
    rows = await service.list_portes_pendientes(empresa_id=current_user.empresa_id)
    return [_redact_porte_for_driver(r, current_user) for r in rows]


@router.post("/", response_model=PorteOut, status_code=status.HTTP_201_CREATED)
async def create_porte(
    porte_in: PorteCreate,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: None = Depends(RoleChecker(["ADMIN", "GESTOR"])),
    service: PortesService = Depends(deps.get_portes_service),
) -> PorteOut:
    try:
        caller_is_owner = str(current_user.rbac_role or "").strip().lower() == "owner"
        return await service.create_porte(
            empresa_id=current_user.empresa_id,
            porte_in=porte_in,
            caller_is_owner=caller_is_owner,
        )
    except PorteDomainError as e:
        detail = str(e)
        if "Límite de crédito excedido" in detail:
            dispatch_webhook(
                empresa_id=str(current_user.empresa_id),
                event_type=WebhookEventType.CREDIT_LIMIT_EXCEEDED.value,
                payload={
                    "cliente_id": str(porte_in.cliente_id),
                    "reason": "hard_stop_credit",
                    "detail": detail,
                },
                background_tasks=background_tasks,
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/cotizar", response_model=PorteCotizarOut)
async def cotizar_porte(
    payload: PorteCotizarIn,
    current_user: UserOut = Depends(deps.get_current_user),
    _: None = Depends(RoleChecker(["ADMIN", "GESTOR"])),
    service: PortesService = Depends(deps.get_portes_service),
) -> PorteCotizarOut:
    if payload.empresa_id is not None and payload.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="empresa_id no coincide con la sesión actual.",
        )
    try:
        out = await service.cotizar_porte(
            empresa_id=current_user.empresa_id,
            origen=payload.origen,
            destino=payload.destino,
            precio_oferta=payload.precio_oferta,
            km_estimados=payload.km_estimados,
            waypoints=payload.waypoints,
        )
        return _mask_porte_cotizar_financials(PorteCotizarOut(**out), current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/facturar",
    response_model=FacturaGenerateResult,
    status_code=status.HTTP_201_CREATED,
)
async def facturar_desde_portes(
    payload: FacturaCreateFromPortes,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: None = Depends(RoleChecker(["ADMIN", "GESTOR"])),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaGenerateResult:
    """
    Factura legal (InvoicePDF + VeriFactu encadenado) vía `FacturasService`
    → `verifactu_service` + `integrations/pdf_adapter` → `pdf_service`.
    """
    try:
        return await facturas.generar_desde_portes(
            empresa_id=current_user.empresa_id,
            payload=payload,
            usuario_id=current_user.usuario_id or current_user.username,
            background_tasks=background_tasks,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


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
    return _redact_porte_for_driver(row, current_user)

