from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import deps
from app.schemas.user import UserOut
from app.services.maps_service import MapsService

router = APIRouter()


@router.get("/distance")
async def distance_km(
    origin: str = Query(..., min_length=1, max_length=500),
    destination: str = Query(..., min_length=1, max_length=500),
    current_user: UserOut = Depends(deps.get_current_user),
    maps: MapsService = Depends(deps.get_maps_service),
) -> dict[str, float]:
    """
    Distancia en km (Distance Matrix + caché). Útil para previsualizar en formularios.
    """
    try:
        km = await maps.get_distance_km(
            origin,
            destination,
            tenant_empresa_id=current_user.empresa_id,
        )
        return {"distance_km": km}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
