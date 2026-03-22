from __future__ import annotations

from pydantic import BaseModel, Field


class VehiculoHuellaMesOut(BaseModel):
    """Agregado mensual de huella por vehículo (para gráficos y PDF)."""

    vehiculo_id: str | None = Field(default=None, description="UUID flota o None si sin asignar")
    matricula: str = Field(..., description="Matrícula o etiqueta")
    etiqueta: str = Field(default="", description="Nombre / tipo motor para leyenda")
    co2_kg: float = Field(..., ge=0, description="kg CO₂eq imputados al vehículo en el mes")
    km_reales: float = Field(..., ge=0, description="Km carretera (Maps / caché) acumulados")


class HuellaCarbonoMensualOut(BaseModel):
    """Resultado de ``calcular_huella_carbono_mensual``."""

    empresa_id: str
    anio: int = Field(..., ge=2000, le=2100)
    mes: int = Field(..., ge=1, le=12)
    total_co2_kg: float = Field(..., ge=0, description="Total kg CO₂eq del periodo")
    total_km_reales: float = Field(..., ge=0, description="Suma km carretera (Distance Matrix + caché)")
    num_portes_facturados: int = Field(..., ge=0)
    media_co2_por_porte_kg: float = Field(
        ...,
        ge=0,
        description="Media kg CO₂ / porte en el mes",
    )
    ahorro_estimado_rutas_optimizadas_kg: float = Field(
        ...,
        ge=0,
        description="vs escenario +15% km (sin optimización de ruta)",
    )
    por_vehiculo: list[VehiculoHuellaMesOut] = Field(
        default_factory=list,
        description="Desglose por vehículo (ordenado por emisiones desc.)",
    )
