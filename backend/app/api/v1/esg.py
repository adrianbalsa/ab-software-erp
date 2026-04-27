from __future__ import annotations

import io
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.esg import EsgMonthlyReportOut, PorteEmissionsCalculatedOut, SustainabilityReportOut
from app.schemas.user import UserOut
from app.services.esg_certificate_service import EsgCertificateService, parse_subject_uuid
from app.services.esg_service import EsgService

router = APIRouter(prefix="/esg")


@router.get(
    "/sustainability-report",
    response_model=SustainabilityReportOut,
    summary="Informe mensual de sostenibilidad (CO₂, benchmark ruta verde, datos Recharts)",
)
async def sustainability_report(
    month: int = Query(..., ge=1, le=12, description="Mes calendario (1–12)"),
    year: int = Query(..., ge=2020, le=2100, description="Año (YYYY)"),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    _quota: None = Depends(deps.check_quota_limit("esg")),
    service: EsgService = Depends(deps.get_esg_service),
) -> SustainabilityReportOut:
    """
    Totales de CO₂ del mes (metodología GLEC alineada con ``calcular_huella_carbono_mensual``)
    frente a un benchmark de «ruta verde teórica», más series listas para gráficos de barras (Recharts).
    """
    return await service.get_company_sustainability_report(
        empresa_id=current_user.empresa_id,
        month=month,
        year=year,
    )


@router.post(
    "/calculate/{porte_id}",
    response_model=PorteEmissionsCalculatedOut,
    summary="Calcular y guardar CO₂ del porte (Euro VI)",
    dependencies=[
        Depends(deps.bind_write_context),
        Depends(deps.check_quota_limit("esg")),
    ],
)
async def calculate_porte_co2(
    porte_id: Annotated[UUID, Path(description="UUID del porte")],
    service: EsgService = Depends(deps.get_esg_service),
) -> PorteEmissionsCalculatedOut:
    """
    Persiste ``portes.co2_kg`` (y ``co2_emitido``) usando distancia satélite si existe,
    Distance Matrix como respaldo y ``km_estimados`` solo en último término (baja confianza).
    """
    try:
        return await service.calculate_porte_emissions(porte_id)
    except ValueError as exc:
        d = str(exc).lower()
        status_code = status.HTTP_404_NOT_FOUND if "no encontrado" in d else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get(
    "/report/{empresa_id}",
    response_model=EsgMonthlyReportOut,
    summary="Reporte ESG mensual agregado por empresa",
)
async def get_monthly_report(
    empresa_id: Annotated[UUID, Path(description="UUID de la empresa")],
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    _quota: None = Depends(deps.check_quota_limit("esg")),
    service: EsgService = Depends(deps.get_esg_service),
) -> EsgMonthlyReportOut:
    if empresa_id != current_user.empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado para esa empresa")
    try:
        return await service.get_monthly_company_report(empresa_id=empresa_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/certificates/{subject_id}/download",
    summary="Certificado ESG (PDF servidor, GLEC v2.0 / ISO 14083, registro auditable)",
)
async def download_esg_certificate_pdf(
    subject_id: str,
    kind: Literal["porte", "factura"] = Query(
        "porte",
        description="porte: UUID del porte; factura: id entero de la factura",
    ),
    official_audit: bool = Query(
        False,
        description="Enterprise: marca el certificado como pending_external_audit (validación oficial solicitada).",
    ),
    current_user: UserOut = Depends(deps.require_write_role("owner", "traffic_manager")),
    _quota: None = Depends(deps.check_quota_limit("esg")),
    service: EsgCertificateService = Depends(deps.get_esg_certificate_service),
) -> StreamingResponse:
    """
    Genera el PDF (porte: ReportLab; factura: FPDF), SHA-256 del binario, QR de verificación pública
    y fila en ``esg_certificate_documents`` / vista ``esg_certificates`` (código UUID + estado).
    """
    eid = str(current_user.empresa_id)
    uid = str(current_user.usuario_id) if current_user.usuario_id else None

    if kind == "porte":
        pid = parse_subject_uuid(subject_id)
        pdf_bytes = await service.generate_porte_certificate_pdf(
            empresa_id=eid,
            porte_id=str(pid),
            usuario_id=uid,
            official_audit=official_audit,
        )
        fname = f"Certificado_Huella_CO2_porte_{str(pid)[:8]}.pdf"
    else:
        try:
            fid = int(str(subject_id).strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ID de factura inválido (entero).",
            ) from exc
        pdf_bytes = await service.generate_factura_certificate_pdf(
            empresa_id=eid,
            factura_id=fid,
            usuario_id=uid,
            official_audit=official_audit,
        )
        fname = f"Certificado_Huella_CO2_factura_{fid}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
