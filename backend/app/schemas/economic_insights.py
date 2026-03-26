from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.finance import FinanceMensualBarOut


class ClienteRentabilidadOut(BaseModel):
    cliente_id: str
    cliente_nombre: str
    ingresos_netos_eur: float = Field(..., ge=0, description="Base imponible acumulada (sin IVA)")
    margen_pct: float = Field(
        ...,
        description="(Ingreso − gasto operativo prorrateado) / ingreso × 100",
    )
    gasto_asignado_eur: float = Field(..., ge=0, description="Gastos totales × participación del cliente")


class GastoCategoriaTreemapOut(BaseModel):
    """Nodo para Treemap: categoría tal cual en `gastos`."""

    name: str
    value: float = Field(..., ge=0)


class MargenKmGasoilMensualOut(BaseModel):
    periodo: str = Field(..., description="YYYY-MM")
    margen_neto_km_eur: float | None = Field(
        default=None,
        description="(Ingresos − gastos operativos del mes) / km facturados en el mes",
    )
    coste_combustible_por_km_eur: float | None = Field(
        default=None,
        description="Gastos netos de combustible del mes / km facturados",
    )


class PuntoEquilibrioOut(BaseModel):
    periodo_referencia: str = Field(..., description="YYYY-MM (mes calendario actual)")
    gastos_fijos_mes_eur: float = Field(..., ge=0)
    gastos_variables_mes_eur: float = Field(..., ge=0)
    ingresos_mes_eur: float = Field(..., ge=0)
    margen_contribucion_ratio: float | None = Field(
        default=None,
        description="(Ingresos − gastos variables) / ingresos si ingresos > 0",
    )
    ingreso_equilibrio_estimado_eur: float | None = Field(
        default=None,
        description="Ingreso mensual mínimo estimado: GF / ratio de contribución",
    )
    km_equilibrio_estimados: float | None = Field(
        default=None,
        description="GF / margen neto por km del mes (si km y margen/km > 0)",
    )
    nota_metodologia: str = Field(
        default="",
        description="Heurística de gastos fijos por categoría (sin campo explícito en BD)",
    )


class AdvancedMetricsMonthRow(BaseModel):
    """KPI mensual: facturación (Math Engine), gastos, ESG (CO₂) y coste/km."""

    periodo: str = Field(..., description="YYYY-MM")
    ingresos_facturacion_eur: float = Field(
        ...,
        description="Suma bases facturadas (sin IVA) reconocidas en el mes",
    )
    gastos_operativos_eur: float = Field(..., ge=0, description="Suma gastos netos (sin IVA) del mes")
    margen_contribucion_eur: float = Field(
        ...,
        description="Ingresos netos − gastos operativos del mes (puede ser negativo)",
    )
    km_portes: float = Field(..., ge=0, description="Suma km_estimados en portes con fecha en el mes")
    gastos_flota_peaje_combustible_eur: float = Field(
        ...,
        ge=0,
        description="Combustible + peajes + mantenimiento (bucket) imputable a operación",
    )
    coste_por_km_eur: float | None = Field(
        default=None,
        description="gastos_flota_peaje_combustible / km_portes",
    )
    emisiones_co2_kg: float = Field(
        ...,
        ge=0,
        description="CO₂ combustible (tickets) + huella estimada portes (kg)",
    )
    emisiones_co2_combustible_kg: float = Field(default=0.0, ge=0)
    emisiones_co2_portes_kg: float = Field(default=0.0, ge=0)
    ebitda_verde_eur_por_kg_co2: float | None = Field(
        default=None,
        description="Ingresos (€) / emisiones CO₂ (kg): eficiencia ESG",
    )


class AdvancedMetricsOut(BaseModel):
    meses: list[AdvancedMetricsMonthRow] = Field(default_factory=list)
    generado_en: str = Field(..., description="Fecha de cálculo ISO (YYYY-MM-DD)")
    nota_metodologia: str = Field(
        default="",
        description="Criterios sin IVA; CO₂ = Scope 1 combustible + huella t·km portes",
    )


class EconomicInsightsOut(BaseModel):
    coste_medio_km_ultimos_30d: float | None = Field(
        default=None,
        description="Gastos operativos netos (30d) / km portes (30d)",
    )
    km_operativos_ultimos_30d: float = Field(..., ge=0)
    gastos_operativos_ultimos_30d: float = Field(..., ge=0)
    top_clientes_rentabilidad: list[ClienteRentabilidadOut] = Field(
        default_factory=list,
        description="Top 5 por mayor margen % (coste prorrateado por volumen de ingreso)",
    )
    ingresos_vs_gastos_mensual: list[FinanceMensualBarOut] = Field(
        default_factory=list,
        description="Últimos 12 meses — ingresos vs gastos totales (áreas)",
    )
    margen_km_vs_gasoil_mensual: list[MargenKmGasoilMensualOut] = Field(
        default_factory=list,
        description="Serie mensual: margen neto/km vs coste combustible/km",
    )
    gastos_por_categoria: list[GastoCategoriaTreemapOut] = Field(
        default_factory=list,
        description="Agregado por categoría de ticket (12 meses)",
    )
    punto_equilibrio_mensual: PuntoEquilibrioOut
