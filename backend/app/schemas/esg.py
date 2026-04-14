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


class EsgAuditReadyRow(BaseModel):
    """Fila de reporte ESG audit-ready por cliente y periodo."""

    periodo: str = Field(..., description="YYYY-MM")
    cliente_id: str = Field(..., description="UUID del cliente")
    cliente_nombre: str | None = Field(default=None, description="Nombre comercial/razón social")
    total_portes: int = Field(..., ge=0)
    total_km_estimados: float = Field(..., ge=0)
    total_co2_kg: float = Field(..., ge=0)
    total_nox_kg: float = Field(..., ge=0)
    metodologia: str = Field(..., description="Resumen de metodología de cálculo")


class EsgAuditReadyOut(BaseModel):
    """Reporte ESG audit-ready: resumen por cliente y periodo."""

    empresa_id: str
    fecha_inicio: str
    fecha_fin: str
    generado_en: str
    total_portes: int = Field(..., ge=0)
    total_km_estimados: float = Field(..., ge=0)
    total_co2_kg: float = Field(..., ge=0)
    total_nox_kg: float = Field(..., ge=0)
    rows: list[EsgAuditReadyRow] = Field(default_factory=list)


class EsgAnnualMemoryExecutiveOut(BaseModel):
    total_co2_kg: float = Field(..., ge=0)
    total_nox_kg: float = Field(..., ge=0)
    total_km: float = Field(..., ge=0)
    eficiencia_media_kg_co2_km: float = Field(..., ge=0)


class EsgAnnualMemoryNormativaOut(BaseModel):
    pct_euro_iii: float = Field(..., ge=0, le=100)
    pct_euro_vi: float = Field(..., ge=0, le=100)


class EsgAnnualMemoryTopClienteOut(BaseModel):
    cliente_id: str
    cliente_nombre: str | None = None
    co2_kg: float = Field(..., ge=0)


class EsgAnnualMemoryOut(BaseModel):
    year: int
    empresa_id: str
    resumen_ejecutivo: EsgAnnualMemoryExecutiveOut
    desglose_normativa: EsgAnnualMemoryNormativaOut
    top_clientes: list[EsgAnnualMemoryTopClienteOut]
    metodologia: str


class PorteEmissionsCalculatedOut(BaseModel):
    """Resultado de ``calculate_porte_emissions`` (motor Euro VI × km reales)."""

    porte_id: str
    distance_km: float = Field(..., ge=0, description="Km usados en el cálculo")
    distance_confidence: str = Field(
        ...,
        description="high: real_distance_meters; medium: Google Distance Matrix; low: km_estimados",
    )
    weight_class: str = Field(..., description="LIGHT | MEDIUM | HEAVY | ARTIC | UNKNOWN")
    euro_vi_factor_kg_per_km: float = Field(..., ge=0, description="Factor Euro VI aplicado (kg/km)")
    co2_kg: float = Field(..., ge=0, description="CO₂e persistido en ``portes.co2_kg``")
    factor_emision_aplicado: float = Field(..., ge=0, description="Factor de emisión aplicado (kg/km)")


class EsgMonthlyReportRowOut(BaseModel):
    month: str = Field(..., description="Mes en formato YYYY-MM")
    total_portes: int = Field(..., ge=0)
    total_distance_km: float = Field(..., ge=0)
    total_co2_kg: float = Field(..., ge=0)
    avg_factor_emision: float = Field(..., ge=0)


class EsgMonthlyReportOut(BaseModel):
    empresa_id: str
    rows: list[EsgMonthlyReportRowOut] = Field(default_factory=list)


class RechartsBarPoint(BaseModel):
    """Serie simple para gráficos de barras (Recharts ``<BarChart data={...} />``)."""

    name: str = Field(..., description="Etiqueta eje X / leyenda")
    value: float = Field(..., ge=0, description="Valor numérico (p. ej. kg CO₂)")
    fill: str | None = Field(
        default=None,
        description="Color CSS opcional para ``<Cell />`` o tema",
    )


class SustainabilityReportOut(BaseModel):
    """
    Informe mensual de sostenibilidad: totales reales vs referencia «ruta verde teórica»
    (km optimista × factor Euro VI bajo), más datos listos para Recharts.
    """

    empresa_id: str
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    total_co2_kg_actual: float = Field(..., ge=0, description="Huella con metodología GLEC mensual")
    total_km_reales: float = Field(..., ge=0)
    num_portes_facturados: int = Field(..., ge=0)
    theoretical_green_route_co2_kg: float = Field(
        ...,
        ge=0,
        description=(
            "Referencia inferior: mismos km × factor mínimo Euro VI ligero (0,70 kg/km). "
            "No es una segunda medición de ruta; sirve de benchmark de eficiencia."
        ),
    )
    green_route_km_factor: float = Field(
        default=0.93,
        ge=0,
        le=1,
        description="Opcional: penalización de km por suboptimización de ruta (env ESG_GREEN_ROUTE_KM_FACTOR).",
    )
    co2_delta_vs_green_kg: float = Field(
        ...,
        description="actual − theoretical_green (positivo = por encima del benchmark).",
    )
    metodologia: str = Field(..., description="Resumen para auditoría / pie de gráfico")
    chart_comparison: list[RechartsBarPoint] = Field(
        default_factory=list,
        description="Dos barras: real vs referencia verde (Benchmark)",
    )
    chart_by_vehicle: list[dict[str, float | str | None]] = Field(
        default_factory=list,
        description="Desglose por vehículo: keys name, co2_kg, km (Recharts)",
    )
