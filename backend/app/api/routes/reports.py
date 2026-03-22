from __future__ import annotations

import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.user import UserOut
from app.services.eco_service import EcoService
from app.services.report_service import ReportService

router = APIRouter()

_PERIODO_YYYY_MM = re.compile(r"^\d{4}-\d{2}$")


@router.get("/facturas/{factura_id}/pdf")
async def descargar_factura_pdf_inmutable(
    factura_id: int,
    current_user: UserOut = Depends(deps.get_current_user),
    report_service: ReportService = Depends(deps.get_report_service),
) -> StreamingResponse:
    """
    PDF VeriFactu **inmutable**: líneas solo desde ``porte_lineas_snapshot`` + ``hash_registro`` + QR.
    """
    try:
        pdf = await report_service.factura_inmutable_pdf_bytes(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="factura no encontrada")
    fid_str = str(factura_id)
    safe = "".join(c for c in fid_str[:36] if c.isalnum() or c in "-_") or "factura"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="factura_{safe}.pdf"',
        },
    )


@router.get("/esg/certificado-huella")
async def descargar_certificado_huella_co2(
    periodo: str = Query(..., description="Mes calendario YYYY-MM"),
    current_user: UserOut = Depends(deps.get_current_user),
    report_service: ReportService = Depends(deps.get_report_service),
    eco_service: EcoService = Depends(deps.get_eco_service),
) -> StreamingResponse:
    """
    Certificado PDF de huella CO₂ (Scope 1) para un mes, vía ``EcoService`` + referencia Euro 6.
    """
    if not _PERIODO_YYYY_MM.match(periodo.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="periodo debe ser YYYY-MM",
        )
    periodo = periodo.strip()
    meses = await eco_service.emisiones_combustible_por_mes(empresa_id=current_user.empresa_id)
    row = next((m for m in meses if m.periodo == periodo), None)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="sin datos de combustible para ese periodo",
        )
    pdf = await report_service.certificado_huella_pdf_bytes(
        empresa_id=current_user.empresa_id,
        periodo=periodo,
        co2_kg_mes=float(row.co2_kg),
        litros_estimados=float(row.litros_estimados),
    )
    fname = f"Certificado_Huella_CO2_{periodo}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
