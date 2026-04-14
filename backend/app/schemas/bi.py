from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BiDashboardSummaryOut(BaseModel):
    """KPIs compactos para tarjetas / dashboard BI."""

    dso_days: float | None = Field(
        default=None,
        description="Días promedio entre emisión de factura y fecha contable del cobro (pares conciliados).",
    )
    dso_sample_size: int = Field(default=0, description="Número de facturas con movimiento bancario emparejado.")
    avg_margin_eur: float | None = Field(
        default=None,
        description="Margen estimado medio (EUR) en portes completados: precio − km×0,62.",
    )
    avg_margin_portes: int = Field(default=0, description="Portes completados usados para el margen medio.")
    total_co2_saved_kg: float | None = Field(
        default=None,
        description="Suma de ahorro CO₂ vs Euro III (kg) en portes completados con dato ESG.",
    )
    co2_saved_portes: int = Field(default=0, description="Portes completados que aportaron a total_co2_saved_kg.")
    avg_efficiency_eur_per_eur_km: float | None = Field(
        default=None,
        description="Media de precio / (km × 0,62) en portes con km > 0 (proxy rentabilidad por intensidad km).",
    )
    efficiency_sample_size: int = Field(default=0)


class ProfitabilityScatterPoint(BaseModel):
    """Punto para ScatterChart (Recharts: dataKey x / y)."""

    porte_id: UUID
    km: float = Field(..., description="Km reales o estimados del porte.")
    margin_eur: float = Field(..., description="Margen estimado EUR (precio − km×0,62).")
    precio_pactado: float | None = None
    estado: str | None = None
    cliente: str | None = Field(default=None, description="Nombre del cliente (maestro).")
    vehiculo: str | None = Field(default=None, description="Matrícula / vehículo de flota asignado.")
    route_label: str | None = Field(default=None, description="Origen–destino legible del porte.")


class BiProfitabilityChartsOut(BaseModel):
    """Serie lista para <ScatterChart data={points} />."""

    points: list[ProfitabilityScatterPoint]
    coste_operativo_eur_km: float = Field(default=0.62, description="Constante usada en el margen estimado.")


class EsgMatrixPoint(BaseModel):
    """Par CO₂ / margen (EBITDA operativo aprox.) por porte completado."""

    porte_id: UUID
    co2_kg: float
    margen_estimado: float = Field(..., description="EUR: precio pactado − km × coste operativo/km.")
    km: float
    route_label: str = Field(default="", description="Etiqueta corta origen–destino.")


class HeatmapCellOut(BaseModel):
    """
    Celda para matrices tipo heatmap (eje X = bins de km, eje Y = bins de margen).
    Compatible con gráficos de celdas o barras agrupadas en Recharts.
    """

    x_bin: str = Field(..., description="Rango de km (etiqueta legible).")
    y_bin: str = Field(..., description="Rango de margen EUR (etiqueta legible).")
    count: int = Field(..., ge=0)
    total_co2_kg: float = Field(default=0.0)


class TreemapNodeOut(BaseModel):
    """Nodo plano para <Treemap data={nodes} /> (Recharts: name, size)."""

    name: str
    size: float = Field(..., description="Área del nodo (p. ej. kg CO₂).")
    margen_estimado: float | None = None
    porte_id: UUID | None = None


class BiEsgImpactChartsOut(BaseModel):
    matrix: list[EsgMatrixPoint]
    heatmap_cells: list[HeatmapCellOut]
    treemap_nodes: list[TreemapNodeOut]
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos opcionales (bins, constantes) para el front.",
    )
