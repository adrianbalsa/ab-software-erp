from __future__ import annotations

from pydantic import BaseModel, Field


class FinanceMensualBarOut(BaseModel):
    """Un mes en la serie comparativa ingresos vs gastos (snake_case)."""

    periodo: str = Field(..., description="YYYY-MM")
    ingresos: float = Field(..., ge=0, description="Ingresos netos sin IVA del mes (facturas)")
    gastos: float = Field(..., ge=0, description="Gastos operativos netos sin IVA del mes")


class FinanceTesoreriaMensualOut(BaseModel):
    """Facturación vs cobros reconocidos en el mismo mes de emisión (proxy de tesorería)."""

    periodo: str = Field(..., description="YYYY-MM")
    ingresos_facturados: float = Field(
        ...,
        ge=0,
        description="Bases facturadas (sin IVA) con fecha de emisión en el mes",
    )
    cobros_reales: float = Field(
        ...,
        ge=0,
        description="Importe de facturas cobradas (estado cobrada) con emisión en el mes",
    )


class GastoBucketCincoOut(BaseModel):
    """Agregado de gastos en 5 categorías operativas para desglose."""

    name: str = Field(..., description="Combustible | Personal | Mantenimiento | Seguros | Peajes")
    value: float = Field(..., ge=0, description="EUR netos sin IVA")


class FinanceDashboardOut(BaseModel):
    """
    KPIs financieros + margen por km (snapshot fiscal) + serie 6 meses.
    """

    ingresos: float = Field(..., description="Total bases imponibles facturadas sin IVA (financial_summary)")
    gastos: float = Field(..., description="Total gastos netos sin IVA")
    ebitda: float = Field(..., description="ingresos − gastos")
    total_km_estimados_snapshot: float = Field(
        ...,
        ge=0,
        description="Suma de total_km_estimados_snapshot en facturas emitidas (inmutable)",
    )
    margen_km_eur: float | None = Field(
        default=None,
        description="EBITDA / total_km_estimados_snapshot si km > 0",
    )
    ingresos_vs_gastos_mensual: list[FinanceMensualBarOut] = Field(
        default_factory=list,
        description="Últimos 6 meses calendario (ingresos desde facturas, gastos desde tickets)",
    )
    tesoreria_mensual: list[FinanceTesoreriaMensualOut] = Field(
        default_factory=list,
        description="Últimos 6 meses: facturado vs cobrado (mismo mes de emisión)",
    )
    gastos_por_bucket_cinco: list[GastoBucketCincoOut] = Field(
        default_factory=list,
        description="Gastos acumulados mapeados a 5 categorías (UI)",
    )
    margen_neto_km_mes_actual: float | None = Field(
        default=None,
        description="(Ingresos − Gastos) / km facturados en el mes en curso",
    )
    margen_neto_km_mes_anterior: float | None = Field(
        default=None,
        description="Mismo KPI para el mes calendario anterior",
    )
    variacion_margen_km_pct: float | None = Field(
        default=None,
        description="Variación % del margen neto/km vs mes anterior (null si no comparable)",
    )
    km_facturados_mes_actual: float | None = Field(
        default=None,
        ge=0,
        description="Suma km (snapshot en facturas) con emisión en el mes en curso",
    )
    km_facturados_mes_anterior: float | None = Field(
        default=None,
        ge=0,
        description="Misma métrica para el mes calendario anterior",
    )


class FinanceSummaryOut(BaseModel):
    """
    KPIs financieros agregados por empresa.

    Importes **sin IVA** (bases y gastos netos de impuesto cuando hay desglose).
    """

    ingresos: float = Field(
        ...,
        description="Suma de bases imponibles de facturas emitidas (sin IVA)",
    )
    gastos: float = Field(
        ...,
        description="Gastos operativos netos sin IVA (total ticket menos cuota iva si consta)",
    )
    ebitda: float = Field(
        ...,
        description="Ingresos netos (sin IVA) − Gastos netos (sin IVA)",
    )
