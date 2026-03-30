"""Optimización de rutas con Google Distance Matrix API y análisis de huella de carbono."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.core.esg_engine import calculate_co2_emissions, get_co2_factor_kg_per_km
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.maps_service import MapsService


router = APIRouter()


class WaypointIn(BaseModel):
    """Punto intermedio en la ruta."""

    address: str = Field(..., min_length=3, description="Dirección del waypoint")
    order: int = Field(..., ge=0, description="Orden en la ruta (0-indexed)")


class OptimizeRouteIn(BaseModel):
    """Request para optimización de ruta."""

    origen: str = Field(..., min_length=3, description="Dirección de origen")
    destino: str = Field(..., min_length=3, description="Dirección de destino")
    waypoints: list[WaypointIn] | None = Field(
        default=None,
        description="Puntos intermedios opcionales",
    )
    vehiculo_id: UUID | None = Field(
        default=None,
        description="ID del vehículo para calcular emisiones específicas",
    )


class RouteOption(BaseModel):
    """Opción de ruta calculada."""

    route_id: int
    distancia_km: float
    tiempo_estimado_min: int
    co2_kg: float = Field(description="Emisiones estimadas de CO₂ en kg")
    nox_g: float = Field(default=0.0, description="Emisiones estimadas de NOx en gramos")
    tiene_peajes: bool
    normativa_euro: str = Field(default="Euro VI", description="Normativa EURO del vehículo")
    factor_co2_kg_per_km: float = Field(description="Factor de emisión kg CO₂/km")


class OptimizeRouteOut(BaseModel):
    """Response con rutas ordenadas por huella de carbono."""

    rutas: list[RouteOption] = Field(description="Rutas ordenadas por menor CO₂")
    ruta_recomendada: RouteOption | None = Field(
        default=None,
        description="Ruta con menor huella de carbono",
    )


async def _fetch_vehiculo_normativa(
    db: SupabaseAsync,
    vehiculo_id: str,
    empresa_id: str,
) -> str:
    """Obtiene la normativa EURO del vehículo."""
    try:
        res: Any = await db.execute(
            db.table("flota")
            .select("normativa_euro")
            .eq("id", vehiculo_id)
            .eq("empresa_id", empresa_id)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if rows:
            return str(rows[0].get("normativa_euro") or "Euro VI").strip()
    except Exception:
        pass
    return "Euro VI"


@router.post("/optimize-route", response_model=OptimizeRouteOut)
async def optimize_route(
    payload: OptimizeRouteIn,
    current_user: UserOut = Depends(deps.get_current_user),
    maps_service: MapsService = Depends(deps.get_maps_service),
    db: SupabaseAsync = Depends(deps.get_db),
) -> OptimizeRouteOut:
    """
    Optimiza ruta usando Google Distance Matrix API y calcula huella de carbono.

    Retorna múltiples opciones de ruta ordenadas por menor CO₂.
    Considera la normativa EURO del vehículo para factores de emisión precisos.
    """
    origen = payload.origen.strip()
    destino = payload.destino.strip()

    if not origen or not destino:
        raise HTTPException(status_code=400, detail="Origen y destino son obligatorios")

    normativa_euro = "Euro VI"
    if payload.vehiculo_id:
        normativa_euro = await _fetch_vehiculo_normativa(
            db=db,
            vehiculo_id=str(payload.vehiculo_id),
            empresa_id=str(current_user.empresa_id),
        )

    factor_co2 = get_co2_factor_kg_per_km(normativa_euro)

    try:
        km, duration_min = await maps_service.get_distance_and_duration(
            origin=origen,
            destination=destino,
            tenant_empresa_id=current_user.empresa_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    co2_kg = calculate_co2_emissions(distancia_km=km, categoria_euro=normativa_euro)

    ruta_principal = RouteOption(
        route_id=1,
        distancia_km=round(km, 2),
        tiempo_estimado_min=duration_min,
        co2_kg=round(co2_kg, 2),
        nox_g=0.0,
        tiene_peajes=False,
        normativa_euro=normativa_euro,
        factor_co2_kg_per_km=round(factor_co2, 4),
    )

    rutas = [ruta_principal]

    if payload.waypoints:
        sorted_waypoints = sorted(payload.waypoints, key=lambda w: w.order)
        addresses = [w.address for w in sorted_waypoints]

        try:
            result = await maps_service.calcular_ruta_optima(
                origen=origen,
                destino=destino,
                waypoints=addresses,
            )
            km_wp = result.get("distancia_km", km)
            dur_wp = result.get("tiempo_estimado_min", duration_min)
            co2_wp = calculate_co2_emissions(
                distancia_km=km_wp,
                categoria_euro=normativa_euro,
            )

            ruta_con_waypoints = RouteOption(
                route_id=2,
                distancia_km=round(km_wp, 2),
                tiempo_estimado_min=dur_wp,
                co2_kg=round(co2_wp, 2),
                nox_g=0.0,
                tiene_peajes=result.get("tiene_peajes", False),
                normativa_euro=normativa_euro,
                factor_co2_kg_per_km=round(factor_co2, 4),
            )
            rutas.append(ruta_con_waypoints)
        except Exception:
            pass

    rutas.sort(key=lambda r: r.co2_kg)

    return OptimizeRouteOut(
        rutas=rutas,
        ruta_recomendada=rutas[0] if rutas else None,
    )
