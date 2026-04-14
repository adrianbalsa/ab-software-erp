from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api import deps
from app.schemas.esg import EsgMonthlyReportOut, PorteEmissionsCalculatedOut, SustainabilityReportOut
from app.schemas.user import UserOut
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
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager", "gestor")),
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
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager", "gestor")),
    _quota: None = Depends(deps.check_quota_limit("esg")),
    service: EsgService = Depends(deps.get_esg_service),
) -> EsgMonthlyReportOut:
    if empresa_id != current_user.empresa_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado para esa empresa")
    try:
        return await service.get_monthly_company_report(empresa_id=empresa_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
