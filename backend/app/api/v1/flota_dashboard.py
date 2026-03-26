"""Dashboard de flota: alertas de mantenimiento por km."""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.fleet_maintenance import (
    AlertaAdministrativaOut,
    MantenimientoAlertaOut,
    MantenimientoRegistrarIn,
    MantenimientoRegistrarOut,
)
from app.schemas.user import UserOut
from app.services.fleet_maintenance_service import FleetMaintenanceService

router = APIRouter()


@router.get(
    "/alertas-mantenimiento",
    response_model=list[Union[MantenimientoAlertaOut, AlertaAdministrativaOut]],
    summary="Alertas de mantenimiento y trámites",
)
async def get_alertas_mantenimiento(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: FleetMaintenanceService = Depends(deps.get_fleet_maintenance_service),
) -> list[Union[MantenimientoAlertaOut, AlertaAdministrativaOut]]:
    """
    Combina:
    - **plan_km**: desgaste = (odometro_actual - ultimo_km_realizado) / intervalo_km.
      Urgencia: CRITICO >95%, ADVERTENCIA >85%, resto OK.
    - **tramite_fecha**: ITV, seguro y tacógrafo (fechas en `public.flota`).
      Urgencia por días hasta vencimiento (UTC).
    """
    return await service.list_alertas_mantenimiento(empresa_id=current_user.empresa_id)


@router.post(
    "/mantenimiento/registrar",
    response_model=MantenimientoRegistrarOut,
    summary="Registrar mantenimiento realizado",
)
async def post_registrar_mantenimiento(
    body: MantenimientoRegistrarIn,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: FleetMaintenanceService = Depends(deps.get_fleet_maintenance_service),
) -> MantenimientoRegistrarOut:
    """
    Fija ``ultimo_km_realizado`` al odómetro actual del vehículo y crea un gasto operativo.
    """
    return await service.registrar_mantenimiento(
        empresa_id=current_user.empresa_id,
        username_empleado=current_user.username,
        payload=body,
    )
