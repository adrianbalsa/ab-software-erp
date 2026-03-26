"""Exportación contable (CSV / Excel) para gestoría."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.user import UserOut
from app.services.accounting_export import AccountingExportService, build_accounting_export

router = APIRouter()


@router.get(
    "/accounting",
    summary="Exportación contable ventas/compras",
)
async def export_accounting(
    fecha_inicio: date = Query(..., description="Inicio inclusive (fecha emisión factura / fecha gasto)"),
    fecha_fin: date = Query(..., description="Fin inclusive"),
    tipo: Literal["ventas", "compras", "ambos"] = Query("ventas"),
    formato: Literal["csv", "excel"] = Query("csv"),
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: AccountingExportService = Depends(deps.get_accounting_export_service),
) -> StreamingResponse:
    """
    Descarga diario de ventas y/o compras (memoria; sin persistir en disco).
    Importes redondeados con ``round_fiat`` (2 decimales).
    """
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser >= fecha_inicio",
        )

    body, media_type, filename = await build_accounting_export(
        service,
        empresa_id=str(current_user.empresa_id),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo=tipo,
        formato=formato,
    )

    return StreamingResponse(
        iter([body]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
