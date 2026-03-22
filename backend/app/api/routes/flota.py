from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.api import deps
from app.schemas.flota import (
    AmortizacionLinealIn,
    AmortizacionLinealOut,
    FlotaAlertaOut,
    FlotaMetricasOut,
    FlotaVehiculoIn,
    FlotaVehiculoOut,
    MantenimientoFlotaCreate,
)
from app.schemas.user import UserOut
from app.services.flota_service import FlotaService

router = APIRouter()


@router.get("/inventario", response_model=list[FlotaVehiculoOut])
async def list_inventario(
    current_user: UserOut = Depends(deps.get_current_user),
    service: FlotaService = Depends(deps.get_flota_service),
) -> list[FlotaVehiculoOut]:
    return await service.list_inventario(empresa_id=current_user.empresa_id)


@router.get("/alerts", response_model=list[FlotaAlertaOut])
async def list_alertas_flota(
    current_user: UserOut = Depends(deps.get_current_user),
    service: FlotaService = Depends(deps.get_flota_service),
) -> list[FlotaAlertaOut]:
    """
    Alertas ITV, seguro y próxima revisión por km (tabla ``flota``).
    Alias REST compatible: `/flota/alerts` (Fase 3 visualización). [cite: 2026-03-22]
    """
    return await service.list_alertas(empresa_id=current_user.empresa_id)


@router.get("/metricas", response_model=FlotaMetricasOut)
async def metricas_flota(
    current_user: UserOut = Depends(deps.get_current_user),
    service: FlotaService = Depends(deps.get_flota_service),
) -> FlotaMetricasOut:
    """% disponible vs % riesgo de parada para gráficos."""
    return await service.metricas_flota(empresa_id=current_user.empresa_id)


@router.get("/export")
async def export_estado_flota(
    current_user: UserOut = Depends(deps.get_current_user),
    service: FlotaService = Depends(deps.get_flota_service),
) -> Response:
    """CSV (UTF-8 BOM, `;`) con vencimientos para taller / Excel."""
    body = await service.export_estado_flota_csv_bytes(empresa_id=current_user.empresa_id)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="estado_flota_ab_logistics.csv"',
        },
    )


@router.post(
    "/inventario/guardar",
    response_model=list[FlotaVehiculoOut],
    status_code=status.HTTP_200_OK,
)
async def guardar_inventario(
    vehiculos_in: list[FlotaVehiculoIn],
    current_user: UserOut = Depends(deps.bind_write_context),
    _quota: None = Depends(deps.check_quota_limit("vehiculos")),
    service: FlotaService = Depends(deps.get_flota_service),
) -> list[FlotaVehiculoOut]:
    return await service.save_inventario(empresa_id=current_user.empresa_id, vehiculos_in=vehiculos_in)


@router.post("/mantenimiento", status_code=status.HTTP_201_CREATED)
async def crear_mantenimiento(
    mantenimiento_in: MantenimientoFlotaCreate,
    current_user: UserOut = Depends(deps.bind_write_context),
    service: FlotaService = Depends(deps.get_flota_service),
) -> dict[str, Any]:
    return await service.add_mantenimiento(
        empresa_id=current_user.empresa_id,
        mantenimiento_in=mantenimiento_in,
    )


@router.post("/amortizacion-lineal", response_model=AmortizacionLinealOut)
async def amortizacion_lineal(
    payload: AmortizacionLinealIn,
    _current_user: UserOut = Depends(deps.get_current_user),
    service: FlotaService = Depends(deps.get_flota_service),
) -> AmortizacionLinealOut:
    return await service.amortizacion_lineal(payload=payload)
