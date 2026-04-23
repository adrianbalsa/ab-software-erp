"""Optimización de rutas con Google Distance Matrix API y análisis de huella de carbono."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.core.esg_engine import calculate_co2_emissions, get_co2_factor_kg_per_km
from app.core.math_engine import MathEngine
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
    peajes_estimados_eur: float = Field(default=0.0, description="Coste estimado de peajes en EUR")
    fuel_cost_estimate: float = Field(default=0.0, description="Estimación coste combustible en EUR")
    total_route_cost: float = Field(default=0.0, description="Coste total de ruta (combustible + peajes)")
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
        truck_main = await maps_service.get_truck_route(
            origin=origen,
            destination=destino,
            emission_type=normativa_euro,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    km = float(truck_main.get("distancia_km") or 0.0)
    duration_min = int(truck_main.get("tiempo_estimado_min") or 0)
    peajes_main = float(truck_main.get("peajes_estimados_eur") or 0.0)
    costs_main = MathEngine.calculate_route_costs(
        distance_km=km,
        toll_cost=peajes_main,
    )
    co2_kg = calculate_co2_emissions(distancia_km=km, categoria_euro=normativa_euro)

    ruta_principal = RouteOption(
        route_id=1,
        distancia_km=round(km, 2),
        tiempo_estimado_min=duration_min,
        co2_kg=round(co2_kg, 2),
        nox_g=0.0,
        tiene_peajes=bool(truck_main.get("tiene_peajes")),
        peajes_estimados_eur=float(costs_main.get("toll_cost") or 0.0),
        fuel_cost_estimate=float(costs_main.get("fuel_cost_estimate") or 0.0),
        total_route_cost=float(costs_main.get("total_route_cost") or 0.0),
        normativa_euro=normativa_euro,
        factor_co2_kg_per_km=round(factor_co2, 4),
    )

    rutas = [ruta_principal]

    if payload.waypoints:
        sorted_waypoints = sorted(payload.waypoints, key=lambda w: w.order)
        addresses = [w.address for w in sorted_waypoints]

        try:
            result = await maps_service.get_truck_route(
                origin=origen,
                destination=destino,
                emission_type=normativa_euro,
                waypoints=addresses,
            )
            km_wp = result.get("distancia_km", km)
            dur_wp = result.get("tiempo_estimado_min", duration_min)
            peajes_wp = float(result.get("peajes_estimados_eur") or 0.0)
            costs_wp = MathEngine.calculate_route_costs(
                distance_km=km_wp,
                toll_cost=peajes_wp,
            )
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
                peajes_estimados_eur=float(costs_wp.get("toll_cost") or 0.0),
                fuel_cost_estimate=float(costs_wp.get("fuel_cost_estimate") or 0.0),
                total_route_cost=float(costs_wp.get("total_route_cost") or 0.0),
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
