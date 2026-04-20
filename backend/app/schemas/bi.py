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
        description="Margen medio (EUR) en portes completados: P&L real (combustible imputado) o fallback km×coste.",
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
    margin_eur: float = Field(
        ...,
        description="Margen P&L EUR: precio − combustible imputado − opex no combustible/km (o fallback km×0,62).",
    )
    margin_estimado_legacy_eur: float | None = Field(
        default=None,
        description="Referencia legacy: precio − km×coste operativo/km (0,62).",
    )
    estimated_margin: bool = Field(
        default=True,
        description="True si no hubo ticket de combustible asignable a vehículo/fecha (margen proxy).",
    )
    allocated_fuel_eur: float | None = Field(
        default=None,
        description="Combustible imputado desde tickets (€); 0 o null si solo estimación.",
    )
    other_opex_eur: float | None = Field(
        default=None,
        description="Opex no combustible (km × factor) cuando hay reparto real de combustible.",
    )
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
    estimated_fallback: bool = Field(
        default=False,
        description="True si el margen mostrado es proxy (sin ticket combustible vinculado).",
    )


class BiEsgImpactChartsOut(BaseModel):
    matrix: list[EsgMatrixPoint]
    heatmap_cells: list[HeatmapCellOut]
    treemap_nodes: list[TreemapNodeOut]
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos opcionales (bins, constantes) para el front.",
    )


class ProfitMarginEsgMonthOverMonthOut(BaseModel):
    """CO₂ equivalente (combustible) vs mes calendario anterior — factor ISO 14083 (kg/L)."""

    anchor_month: str = Field(..., description="Mes de referencia YYYY-MM (según `date_to` o hoy).")
    previous_month: str = Field(..., description="Mes calendario inmediatamente anterior.")
    iso_14083_kg_co2_per_litre: float = Field(default=2.67, description="Factor normativo kg CO₂eq / L diésel A.")
    litros_implied_current: float = Field(..., description="Litros estimados desde tickets combustible (EUR / ref €/L).")
    litros_implied_previous: float = Field(..., description="Mismo criterio para el mes anterior.")
    co2_kg_current: float = Field(..., description="Emisiones equivalentes mes actual (litros × factor ISO).")
    co2_kg_previous: float = Field(..., description="Emisiones equivalentes mes anterior.")
    co2_saved_vs_previous_kg: float = Field(
        ...,
        description="Reducción de emisiones vs mes anterior (max(0, anterior − actual)); ahorro climático operativo.",
    )


class ProfitMarginPeriodRowOut(BaseModel):
    """Un bucket temporal para series Recharts (Barras / Waterfall)."""

    period_key: str = Field(..., description="Clave estable: YYYY-MM o YYYY-Www (ISO).")
    period_label: str = Field(..., description="Etiqueta legible para el eje X.")
    ingresos_totales: float = Field(..., description="Suma precio pactado portes (EUR, HALF_EVEN en agregación).")
    gastos_combustible: float = Field(..., description="Gastos bucket combustible (EUR netos sin IVA).")
    gastos_peajes: float = Field(..., description="Gastos bucket peajes (EUR).")
    gastos_otros: float = Field(..., description="Resto de gastos operativos (EUR).")
    gastos_totales: float = Field(..., description="Suma de los tres buckets (EUR).")
    margen_neto: float = Field(..., description="ingresos_totales − gastos_totales (EUR, ROUND_HALF_EVEN).")


class ProfitMarginTotalsOut(BaseModel):
    """Totales del rango solicitado (misma semántica que sumar `series` periodo a periodo)."""

    ingresos_totales: float
    gastos_combustible: float
    gastos_peajes: float
    gastos_otros: float
    gastos_totales: float
    margen_neto: float


class ProfitMarginAnalyticsOut(BaseModel):
    """
    Agregado P&amp;L operativo (portes + gastos) listo para BI en tiempo casi real.
    CSV export y webhooks salientes deben reutilizar las mismas claves que ``series`` / ``totals_rango``.
    """

    granularity: str = Field(..., description="`month` o `week`.")
    series: list[ProfitMarginPeriodRowOut]
    totals_rango: ProfitMarginTotalsOut
    esg_month_over_month: ProfitMarginEsgMonthOverMonthOut | None = Field(
        default=None,
        description="Comparativa CO₂ combustible (ISO 14083) entre el mes ancla y el anterior.",
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Incluye `webhook_event_type` para informes automáticos y filtros aplicados.",
    )
