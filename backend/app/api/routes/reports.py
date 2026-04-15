from __future__ import annotations

import io
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.user import UserOut
from app.services.advisor_service import gather_advisor_context, mask_advisor_context_for_rbac
from app.services.audit_logs_service import AuditLogsService
from app.services.bi_service import BiService
from app.services.eco_service import EcoService
from app.services.finance_service import FinanceService
from app.services.maps_service import MapsService
from app.services.portes_service import PortesService
from app.services.report_service import ReportService
from app.db.supabase import SupabaseAsync

router = APIRouter()

_PERIODO_YYYY_MM = re.compile(r"^\d{4}-\d{2}$")


@router.get("/facturas/{factura_id}/pdf")
async def descargar_factura_pdf_inmutable(
    factura_id: int,
    current_user: UserOut = Depends(deps.require_role("owner")),
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
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
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


@router.get("/efficiency/{empresa_id}")
async def descargar_reporte_eficiencia_flota(
    empresa_id: UUID,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    report_service: ReportService = Depends(deps.get_report_service),
    db: SupabaseAsync = Depends(deps.get_db),
    finance: FinanceService = Depends(deps.get_finance_service),
    portes: PortesService = Depends(deps.get_portes_service),
    audit_logs: AuditLogsService = Depends(deps.get_audit_logs_service),
    maps: MapsService = Depends(deps.get_maps_service),
    bi: BiService = Depends(deps.get_bi_service),
) -> StreamingResponse:
    eid = str(empresa_id)
    if eid != str(current_user.empresa_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="empresa_id no coincide con la sesion actual",
        )

    advisor_context = await gather_advisor_context(
        db=db,
        empresa_id=eid,
        finance=finance,
        portes=portes,
        audit_logs=audit_logs,
        maps=maps,
        bi=bi,
    )
    advisor_context = mask_advisor_context_for_rbac(
        advisor_context,
        rbac_role=str(current_user.rbac_role or ""),
    )
    pdf = await report_service.fleet_efficiency_pdf_bytes(
        empresa_id=eid,
        advisor_context=advisor_context,
    )
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Fleet_Efficiency_Audit_{eid}.pdf"',
        },
    )
