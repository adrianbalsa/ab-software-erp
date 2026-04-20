"""
Rutas fiscales auxiliares (p. ej. exportación AEAT).

El envío de factura por correo (PDF adjunto, Resend) se dispara en segundo plano
desde ``POST /facturas/desde-portes`` al emitir la factura, si ``clientes.email``
está relleno y la API de correo está configurada. Ver ``app.api.routes.facturas``.
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.user import UserOut
from app.services.facturas_service import FacturasService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/exportar-aeat/")
async def exportar_aeat_inspeccion(
    lang: str | None = Query(
        default=None,
        description="Idioma de cabeceras CSV y nombres en ZIP: es | en (por defecto preferencia de usuario).",
    ),
    current_user: UserOut = Depends(deps.require_admin_user),
    _plan: None = Depends(deps.check_quota_limit("exportacion_aeat")),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> StreamingResponse:
    """
    Exportación fiscal para inspección AEAT: CSV de facturas + JSON cadena VeriFactu en ZIP.
    Solo administradores del tenant; planes PRO o Enterprise.
    """
    eff_lang = lang or getattr(current_user, "preferred_language", None) or "es"
    body, filename, n_facturas = await service.exportar_aeat_inspeccion_zip(
        empresa_id=current_user.empresa_id,
        lang=eff_lang,
    )
    logger.critical(
        "EXPORTACION_AEAT_INSPECCION empresa_id=%s username=%s rol=%s facturas=%d fichero=%s",
        str(current_user.empresa_id),
        current_user.username,
        current_user.rol,
        n_facturas,
        filename,
    )
    return StreamingResponse(
        io.BytesIO(body),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
