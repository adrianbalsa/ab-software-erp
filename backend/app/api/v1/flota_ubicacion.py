"""Fleet: actualización rápida de posición GPS (``vehiculos``)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api import deps
from app.schemas.flota import FlotaLiveTrackingOut
from app.schemas.user import UserOut
from app.services.flota_service import FlotaService

router = APIRouter()


@router.get(
    "/live-tracking",
    response_model=list[FlotaLiveTrackingOut],
    summary="Listado flota en tiempo real",
)
async def live_tracking(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: FlotaService = Depends(deps.get_flota_service),
) -> list[FlotaLiveTrackingOut]:
    """
    Posiciones GPS recientes y estado operativo (Disponible / En Ruta / Taller).
    Incluye conductor asignado vía perfil cuando aplica.
    """
    return await service.list_live_tracking(empresa_id=str(current_user.empresa_id))


class VehiculoUbicacionIn(BaseModel):
    latitud: float = Field(..., ge=-90, le=90)
    longitud: float = Field(..., ge=-180, le=180)


def _puede_actualizar_ubicacion(user: UserOut, vehiculo_id: UUID) -> bool:
    if user.rbac_role in ("owner", "traffic_manager"):
        return True
    if user.rbac_role == "driver":
        return user.assigned_vehiculo_id is not None and user.assigned_vehiculo_id == vehiculo_id
    return False


@router.patch(
    "/{vehiculo_id}/ubicacion",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Actualizar posición GPS del vehículo",
)
async def patch_vehiculo_ubicacion(
    vehiculo_id: UUID,
    body: VehiculoUbicacionIn,
    current_user: UserOut = Depends(deps.bind_write_context),
    service: FlotaService = Depends(deps.get_flota_service),
) -> Response:
    """
    Actualiza latitud/longitud del vehículo (conductores: solo su vehículo asignado;
    owner/traffic_manager: cualquier vehículo del tenant).
    """
    if not _puede_actualizar_ubicacion(current_user, vehiculo_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para actualizar la ubicación de este vehículo.",
        )
    try:
        await service.update_ubicacion_gps(
            empresa_id=str(current_user.empresa_id),
            vehiculo_id=str(vehiculo_id),
            latitud=body.latitud,
            longitud=body.longitud,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
