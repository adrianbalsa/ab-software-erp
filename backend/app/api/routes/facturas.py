from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from starlette.requests import Request

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.factura import (
    FacturaCreateFromPortes,
    FacturaEmailEnviadaOut,
    FacturaGenerateResult,
    FacturaOut,
    FacturaRecalculateIn,
    FacturaRecalculateOut,
    FacturaRectificarIn,
)
from app.schemas.user import UserOut
from app.services.auditoria_service import AuditoriaService
from app.services.email_service import EmailService, send_email_background_task, send_invoice_email_from_base64
from app.services.facturas_service import FacturasService
from pydantic import BaseModel


router = APIRouter()
_log = logging.getLogger(__name__)


class FacturaQueueOut(BaseModel):
    status: str
    job_id: str
    factura_id: int
    aeat_sif_estado: str


@router.post(
    "/{factura_id}/recalcular-totales",
    response_model=FacturaRecalculateOut,
)
async def recalcular_totales_factura(
    factura_id: int,
    payload: FacturaRecalculateIn = FacturaRecalculateIn(),
    current_user: UserOut = Depends(deps.bind_write_context),
    _: None = Depends(deps.RoleChecker(["admin", "gestor"])),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaRecalculateOut:
    """
    Recalcula base / IVA / total con MathEngine (Decimal, ROUND_HALF_EVEN) desde el snapshot.
    No persiste; rechaza si ya hay huella VeriFactu en la factura.
    """
    try:
        return await service.recalculate_invoice(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
            global_discount=Decimal(str(payload.global_discount)),
            aplicar_recargo_equivalencia=payload.aplicar_recargo_equivalencia,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/", response_model=list[FacturaOut])
async def list_facturas(
    estado_aeat: str | None = Query(
        None,
        description="Filtrar por columna aeat_sif_estado (p. ej. aceptado, pendiente).",
    ),
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: FacturasService = Depends(deps.get_facturas_service_async),
) -> list[FacturaOut]:
    return await service.list_facturas(
        empresa_id=current_user.empresa_id,
        estado_aeat=estado_aeat,
    )


@router.get("/{factura_id}", response_model=FacturaOut)
async def obtener_factura(
    factura_id: int,
    current_user: UserOut = Depends(deps.require_role("owner")),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="facturas", path_param="factura_id")
    ),
    service: FacturasService = Depends(deps.get_facturas_service_async),
) -> FacturaOut:
    """Detalle de factura por id (misma empresa que el usuario)."""
    try:
        return await service.get_factura(empresa_id=current_user.empresa_id, factura_id=factura_id)
    except ValueError as e:
        msg = str(e).lower()
        if "no encontrada" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/desde-portes",
    response_model=FacturaGenerateResult,
    status_code=status.HTTP_201_CREATED,
)
async def generar_factura_desde_portes(
    request: Request,
    payload: FacturaCreateFromPortes,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: None = Depends(deps.RoleChecker(["admin", "gestor"])),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaGenerateResult:
    try:
        result = await service.generar_desde_portes(
            empresa_id=current_user.empresa_id,
            payload=payload,
            usuario_id=current_user.usuario_id or current_user.username,
            background_tasks=background_tasks,
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
            "preferred_language": getattr(current_user, "preferred_language", None) or "es",
        }
        request.state.audit_payload_supplement = {
            "delegado_segundo_plano": True,
            "operacion": "factura_emitida_envio_pdf_cliente_resend",
            "mensaje": "Email encolado para envío en segundo plano",
        }
        _log.info("Email encolado para envío en segundo plano")
        background_tasks.add_task(
            send_email_background_task,
            "ENVIAR_FACTURA_PDF_RESEND",
            partial(
                send_invoice_email_from_base64,
                factura_data,
                result.pdf_base64,
                dest,
                getattr(current_user, "preferred_language", None) or "es",
            ),
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
    _: None = Depends(deps.RoleChecker(["admin", "gestor"])),
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


@router.post(
    "/{factura_id}/enviar",
    response_model=FacturaEmailEnviadaOut,
    summary="Enviar factura por correo (SMTP)",
)
async def enviar_factura_por_email(
    factura_id: int,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="facturas", path_param="factura_id")
    ),
    service: FacturasService = Depends(deps.get_facturas_service),
    db: SupabaseAsync = Depends(deps.get_db),
) -> FacturaEmailEnviadaOut:
    """
    Genera el PDF al vuelo (misma pipeline que ``GET …/pdf-data``), obtiene el email del cliente
    y envía el documento por **SMTP** si está configurado (``SMTP_*``, ``EMAILS_FROM_EMAIL``).

    Registra un evento best-effort en ``auditoria`` con la marca temporal del envío.
    """
    if not EmailService.smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio SMTP no configurado (SMTP_HOST, SMTP_PORT, EMAILS_FROM_EMAIL).",
        )
    try:
        numero_factura, dest_email = await service.resolve_destinatario_email_factura(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    try:
        pdf_bytes = await service.generate_factura_pdf_bytes(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
        )
    except ValueError as e:
        if "no encontrada" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    mailer = EmailService()
    try:
        await mailer.send_invoice_email(
            dest_email,
            pdf_bytes,
            numero_factura,
            lang=getattr(current_user, "preferred_language", None) or "es",
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e

    enviado_en = datetime.now(tz=timezone.utc)
    audit = AuditoriaService(db)
    await audit.try_log(
        empresa_id=str(current_user.empresa_id),
        accion="ENVIAR_FACTURA_EMAIL",
        tabla="facturas",
        registro_id=str(factura_id),
        cambios={
            "numero_factura": numero_factura,
            "destinatario": dest_email,
            "enviado_en": enviado_en.isoformat(),
            "canal": "smtp",
        },
    )

    return FacturaEmailEnviadaOut(
        factura_id=factura_id,
        numero_factura=numero_factura,
        destinatario=dest_email,
        enviado_en=enviado_en,
        mensaje="Factura enviada por correo correctamente.",
        auditoria={
            "accion": "ENVIAR_FACTURA_EMAIL",
            "tabla": "facturas",
            "registro_id": str(factura_id),
            "enviado_en": enviado_en.isoformat(),
        },
    )


@router.post("/{factura_id}/finalizar", response_model=FacturaOut)
async def finalizar_factura_verifactu(
    factura_id: int,
    background_tasks: BackgroundTasks,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: None = Depends(deps.RoleChecker(["admin", "gestor"])),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaOut:
    """
    Finaliza el registro VeriFactu: cadena ``fingerprint``, URL SREI en ``qr_code_url`` y
    ``is_finalized`` (inmutable para edición/borrado según trigger en BD).
    """
    try:
        return await service.finalizar_factura_verifactu(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
            usuario_id=current_user.usuario_id or current_user.username,
            background_tasks=background_tasks,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{factura_id}/reenviar-aeat",
    response_model=FacturaQueueOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reenviar_factura_aeat(
    factura_id: int,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: None = Depends(deps.RoleChecker(["admin", "gestor"])),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaQueueOut:
    """
    Reintenta el envío del registro a la AEAT (p. ej. tras caída de red o corrección de certificado).
    En desarrollo solo se usa la URL de pruebas si ``AEAT_BLOQUEAR_PROD_EN_DESARROLLO`` está activo.
    """
    try:
        out = await service.reenviar_aeat_sif(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
            usuario_id=current_user.usuario_id or current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FacturaQueueOut.model_validate(out)
