import re
from typing import Any

from fastapi import APIRouter, Depends

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.fleet import TruckEfficiencyOut
from app.schemas.user import UserOut

from pydantic import BaseModel

class HTTPError(BaseModel):
    detail: str

router = APIRouter()

def normalize_matricula(m: str) -> str:
    if not m:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(m).upper())

@router.get(
    "/efficiency-ranking",
    response_model=list[TruckEfficiencyOut],
    summary="Ranking de eficiencia de la flota",
    responses={
        404: {"description": "No encontrado", "model": HTTPError},
        400: {"description": "Petición inválida", "model": HTTPError}
    }
)
async def get_fleet_efficiency_ranking(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> list[TruckEfficiencyOut]:
    """
    Cruza vehiculos con portes y facturas de gastos (repostajes) para calcular:
    - km totales, litros totales, consumo medio, coste por km, margen generado, y alerta de mantenimiento (si ha superado 30.000 km desde la última revisión).
    """
    empresa_id = str(current_user.empresa_id)

    # 1. Fetch flota (vehiculos)
    res_flota: Any = await db.execute(
        db.table("flota")
        .select("id, matricula, vehiculo, km_actual, odometro_actual")
        .eq("empresa_id", empresa_id)
        .is_("deleted_at", "null")
    )
    flota_rows = (res_flota.data or []) if hasattr(res_flota, "data") else []

    # 2. Fetch portes
    res_portes: Any = await db.execute(
        db.table("portes")
        .select("vehiculo_id, km_estimados, precio_pactado")
        .eq("empresa_id", empresa_id)
        .is_("deleted_at", "null")
    )
    portes_rows = (res_portes.data or []) if hasattr(res_portes, "data") else []

    # 3. Fetch gastos_vehiculo (gastos de combustible / facturas asociadas a matrícula)
    res_gastos: Any = await db.execute(
        db.table("gastos_vehiculo")
        .select("matricula_normalizada, litros, importe_total, categoria")
        .eq("empresa_id", empresa_id)
        .is_("deleted_at", "null")
    )
    gastos_rows = (res_gastos.data or []) if hasattr(res_gastos, "data") else []

    # 4. Fetch planes de mantenimiento (para revisiones)
    res_planes: Any = await db.execute(
        db.table("planes_mantenimiento")
        .select("vehiculo_id, ultimo_km_realizado")
        .eq("empresa_id", empresa_id)
        .in_("tipo_tarea", ["Revisión", "Mecánica General"]) # Filtro genérico para revisiones
    )
    planes_rows = (res_planes.data or []) if hasattr(res_planes, "data") else []

    # Map planes to vehicle for last maintenance km
    last_revision_by_vid = {}
    for p in planes_rows:
        vid = str(p.get("vehiculo_id"))
        ukm = int(p.get("ultimo_km_realizado") or 0)
        # Tomar el km más alto de mantenimiento si hay varios
        if vid not in last_revision_by_vid or ukm > last_revision_by_vid[vid]:
            last_revision_by_vid[vid] = ukm

    # Aggregate Portes
    portes_by_vid = {}
    for p in portes_rows:
        vid = str(p.get("vehiculo_id"))
        km = float(p.get("km_estimados") or 0.0)
        revenue = float(p.get("precio_pactado") or 0.0)
        if vid not in portes_by_vid:
            portes_by_vid[vid] = {"km": 0.0, "revenue": 0.0}
        portes_by_vid[vid]["km"] += km
        portes_by_vid[vid]["revenue"] += revenue

    # Aggregate Gastos by normalized matricula
    gastos_by_mat = {}
    for g in gastos_rows:
        mat_norm = normalize_matricula(g.get("matricula_normalizada") or "")
        litros = float(g.get("litros") or 0.0)
        importe = float(g.get("importe_total") or 0.0)
        if mat_norm not in gastos_by_mat:
            gastos_by_mat[mat_norm] = {"litros": 0.0, "importe": 0.0}
        gastos_by_mat[mat_norm]["litros"] += litros
        gastos_by_mat[mat_norm]["importe"] += importe

    results = []
    for f in flota_rows:
        vid = str(f.get("id"))
        mat = str(f.get("matricula") or "")
        mat_norm = normalize_matricula(mat)
        marca_modelo = str(f.get("vehiculo") or "Desconocido")
        
        # Odometer
        odo = float(f.get("odometro_actual") or f.get("km_actual") or 0.0)
        
        # Data from portes
        p_data = portes_by_vid.get(vid, {"km": 0.0, "revenue": 0.0})
        # If odometer not set, fallback to summed km from portes
        km_totales = odo if odo > 0 else p_data["km"]
        
        # Data from expenses
        g_data = gastos_by_mat.get(mat_norm, {"litros": 0.0, "importe": 0.0})
        litros_totales = g_data["litros"]
        gastos_totales = g_data["importe"]
        
        # Consumption
        # Consumo medio = litros / (km / 100)
        # Using km_totales might be wrong if it tracks all history but fuel is only partial,
        # but following instructions: "Calcula el consumo medio basado en los repostajes registrados"
        # Since we have liters, usually average consumption is based on the km. If km is 0, it's 0.
        consumo_medio = 0.0
        if km_totales > 0:
            consumo_medio = (litros_totales / km_totales) * 100.0
            
        # Cost per km
        coste_por_km = 0.0
        if km_totales > 0:
            coste_por_km = gastos_totales / km_totales
            
        # Margen = revenue from portes - expenses
        margen_generado = p_data["revenue"] - gastos_totales
        
        # Alerta mantenimiento > 30.000 km
        last_km = last_revision_by_vid.get(vid, 0)
        alerta_mantenimiento = (km_totales - last_km) > 30000.0

        results.append(
            TruckEfficiencyOut(
                matricula=mat,
                marca_modelo=marca_modelo,
                km_totales=round(km_totales, 2),
                litros_totales=round(litros_totales, 2),
                consumo_medio=round(consumo_medio, 2),
                coste_por_km=round(coste_por_km, 4),
                alerta_mantenimiento=alerta_mantenimiento,
                margen_generado=round(margen_generado, 2),
            )
        )

    # Sort by margin descending as it is a ranking
    results.sort(key=lambda x: x.margen_generado, reverse=True)
    
    return results
