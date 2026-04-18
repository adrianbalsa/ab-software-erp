from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FinanceMensualBarOut(BaseModel):
    """Punto mensual de la serie operativa ingresos vs gastos (P&L de caja operativa aproximada)."""

    periodo: str = Field(
        ...,
        description="Mes calendario en formato YYYY-MM; siempre incluido aunque no haya movimiento (0,00).",
    )
    ingresos: float = Field(
        ...,
        ge=0,
        description="Reconocimiento de ingreso neto sin IVA del mes: suma de bases imponibles o "
        "(total_factura − cuota_iva) de facturas con fecha de emisión en el mes.",
    )
    gastos: float = Field(
        ...,
        ge=0,
        description="Gastos operativos netos sin IVA del mes: tickets en `gastos` con fecha en el mes "
        "(importe total menos cuota IVA cuando consta).",
    )


class FinanceTesoreriaMensualOut(BaseModel):
    """
    Comparativa mensual **facturación** (emisión) vs **entradas bancarias** (fecha de apunte).

    Útil en Due Diligence para contrastar reconocimiento contable de ingresos con liquidez efectiva.
    """

    periodo: str = Field(
        ...,
        description="Mes calendario YYYY-MM del año fiscal en curso (enero–diciembre); siempre presente.",
    )
    ingresos_facturados: float = Field(
        ...,
        ge=0,
        description="Ingreso neto sin IVA facturado en el mes (misma regla que el bar de ingresos, "
        "agrupado por `fecha_emision`).",
    )
    cobros_reales: float = Field(
        ...,
        ge=0,
        description="Suma de importes de movimientos bancarios conciliados (``bank_transactions.reconciled``) "
        "en el mes del ``booked_date``, vinculados a facturas cobradas vía ``matched_transaction_id`` / ``pago_id`` "
        "(flujo GoCardless / Open Banking). Sin histórico bancario, el backend devuelve 0,00.",
    )


class GastoBucketCincoOut(BaseModel):
    """Desglose de gastos operativos en cinco buckets homogéneos para reporting ejecutivo y comparables entre tenants."""

    name: str = Field(
        ...,
        description="Bucket fijo: Combustible | Personal | Mantenimiento | Seguros | Peajes. "
        "Combustible incluye tickets enlazados a `gastos_vehiculo` (importación tarjeta combustible) "
        "además de categorías con palabra clave combustible.",
    )
    value: float = Field(
        ...,
        ge=0,
        description="Acumulado YTD (año calendario del `hoy` de la petición) en EUR netos sin IVA para ese bucket.",
    )


class FinanceDashboardOut(BaseModel):
    """
    Panel financiero consolidado por empresa (tenant): P&L mensual, tesorería, desglose de gastos y margen por km.

    Los importes siguen política **sin IVA** alineada con `FinanceService`. Las series temporales están
    densificadas (sin huecos nulos) para consumo estable en frontends y exportaciones auditoría.
    """

    ingresos: float = Field(
        ...,
        description="Ingresos netos sin IVA del **period_month** solicitado (o mes en curso): suma de facturas "
        "emitidas en ese mes calendario.",
    )
    gastos: float = Field(
        ...,
        description="Gastos operativos netos sin IVA del mismo mes calendario que `ingresos` (tabla `gastos`).",
    )
    ebitda: float = Field(
        ...,
        description="Resultado operativo aproximado del mes: `ingresos − gastos` (mismas reglas netas de IVA).",
    )
    total_km_estimados_snapshot: float = Field(
        ...,
        ge=0,
        description="Kilómetros facturados congelados al emitir (`total_km_estimados_snapshot`) sumados en el mes "
        "de emisión; base para margen €/km fiscal.",
    )
    margen_km_eur: float | None = Field(
        default=None,
        description="Margen operativo por km del mes: `ebitda / total_km_estimados_snapshot` si km > 0; "
        "en otro caso `null` (evita división por cero).",
    )
    ingresos_vs_gastos_mensual: list[FinanceMensualBarOut] = Field(
        default_factory=list,
        description="Ventana móvil de **6 meses** terminando en el mes de `hoy`: siempre 6 filas ordenadas "
        "cronológicamente; meses sin actividad muestran 0,00 en ingresos y gastos.",
    )
    tesoreria_mensual: list[FinanceTesoreriaMensualOut] = Field(
        default_factory=list,
        description="Serie de **12 meses** del año calendario de `hoy`: facturación neta del mes vs cobros "
        "bancarios conciliados en ese mes (`booked_date`). Sin movimientos bancarios importados para la empresa, "
        "`cobros_reales` es 0,00 en todos los meses.",
    )
    gastos_por_bucket_cinco: list[GastoBucketCincoOut] = Field(
        default_factory=list,
        description="Siempre **5 elementos** fijos (orden estable) para evitar errores de UI; importe 0,00 si "
        "no hay gastos en el bucket en el año en curso.",
    )
    margen_neto_km_mes_actual: float | None = Field(
        default=None,
        description="Margen neto operativo por km del mes del `period_month`: (ingresos − gastos) / km facturados; "
        "`null` si no hay km.",
    )
    margen_neto_km_mes_anterior: float | None = Field(
        default=None,
        description="Mismo KPI para el mes calendario inmediatamente anterior al de `period_month`.",
    )
    variacion_margen_km_pct: float | None = Field(
        default=None,
        description="Variación porcentual `(margen_actual − margen_anterior) / margen_anterior` cuando el "
        "denominador es distinto de cero; `null` si no es comparable.",
    )
    km_facturados_mes_actual: float | None = Field(
        default=None,
        ge=0,
        description="Suma de `total_km_estimados_snapshot` en facturas con emisión en el mes de `period_month`.",
    )
    km_facturados_mes_anterior: float | None = Field(
        default=None,
        ge=0,
        description="Igual que `km_facturados_mes_actual` para el mes calendario previo.",
    )


class FinanceSummaryOut(BaseModel):
    """
    KPIs financieros agregados por empresa y **mes calendario** (YYYY-MM).

    Importes **sin IVA**: mismas reglas que el dashboard transaccional; datos en vivo desde
    ``facturas`` y ``gastos`` (no snapshots preagregados).
    """

    ingresos: float = Field(
        ...,
        description="Suma de ingresos netos sin IVA del mes: ``base_imponible`` o "
        "``total_factura − cuota_iva`` por factura con ``fecha_emision`` en el mes.",
    )
    gastos: float = Field(
        ...,
        description="Suma de gastos operativos netos sin IVA del mes (tabla ``gastos``, fecha en el mes; "
        "importe total menos cuota IVA cuando consta).",
    )
    ebitda: float = Field(
        ...,
        description="Resultado operativo aproximado del mes: ``ingresos − gastos``.",
    )


class TreasuryRiskTrendPointOut(BaseModel):
    """Punto mensual para series de tesorería/riesgo (6 meses)."""

    periodo: str = Field(..., description="YYYY-MM")
    cobrado: float = Field(..., ge=0, description="Importe cobrado del mes")
    pendiente: float = Field(..., ge=0, description="Importe pendiente del mes")


class TreasuryRiskDashboardOut(BaseModel):
    """KPIs ejecutivos de tesorería y riesgo de cobro."""

    total_pendiente: float = Field(..., ge=0, description="Total pendiente de cobro")
    garantizado_sepa: float = Field(
        ...,
        ge=0,
        description="Pendiente de clientes con mandato SEPA activo",
    )
    en_riesgo_alto: float = Field(
        ...,
        ge=0,
        description="Pendiente asociado a clientes con score de riesgo > 7",
    )
    cashflow_trend: list[TreasuryRiskTrendPointOut] = Field(
        default_factory=list,
        description="Serie últimos 6 meses con cobrado y pendiente",
    )
    fuente_datos: str = Field(
        ...,
        description="Origen del agregado: facturas o portes (fallback)",
    )


class CreditAlertOut(BaseModel):
    """Alerta proactiva por consumo de límite de crédito (≥80 %)."""

    cliente_id: str = Field(..., description="UUID del cliente (tenant)")
    nombre_cliente: str = Field(..., description="Razón social o nombre comercial")
    saldo_pendiente: float = Field(..., ge=0, description="EUR pendientes de cobro (facturas o portes no cobrados)")
    limite_credito: float = Field(..., ge=0, description="Límite de crédito configurado (EUR)")
    porcentaje_consumo: float = Field(..., ge=0, description="Consumo del límite (%) con 2 decimales")
    nivel_alerta: Literal["WARNING", "CRITICAL"] = Field(
        ...,
        description="WARNING: 80–99 %; CRITICAL: ≥100 %",
    )


class RouteMarginRowOut(BaseModel):
    """
    Ranking de margen neto por ruta (M_n): ingresos vs coste operativo estimado por km.
    """

    ruta: str = Field(..., description='Ruta legible, ej. "Madrid - Barcelona"', examples=["Madrid - Barcelona"])
    total_portes: int = Field(..., ge=0, description="Número de portes agregados en la ruta", examples=[45])
    ingresos_totales: float = Field(..., description="Suma de precio_pactado (EUR sin IVA)", examples=[45000.0])
    costes_totales: float = Field(..., ge=0, description="Suma de km aplicables × coste operativo / km", examples=[32000.0])
    margen_neto: float = Field(..., description="ingresos_totales − costes_totales", examples=[13000.0])
    margen_porcentual: float = Field(
        ...,
        description="(margen_neto / ingresos_totales) × 100 si ingresos > 0; si no, 0",
        examples=[28.8]
    )


class RiskRankingRowOut(BaseModel):
    """
    Ranking de riesgo por cliente: V_r = saldo_pendiente × (riesgo_score / 10).
    """

    cliente_id: str = Field(..., description="UUID del cliente (tenant)", examples=["123e4567-e89b-12d3-a456-426614174000"])
    nombre: str = Field(..., description="Razón social o nombre comercial", examples=["Logística del Sur S.L."])
    saldo_pendiente: float = Field(..., ge=0, description="EUR pendientes de cobro (facturas o portes no cobrados)", examples=[15400.50])
    riesgo_score: float = Field(..., ge=0, le=10, description="Score operativo 0–10", examples=[8.5])
    valor_riesgo: float = Field(..., ge=0, description="V_r = saldo_pendiente × (riesgo_score / 10)", examples=[13090.42])
    mandato_sepa_activo: bool = Field(
        ...,
        description="Mandato SEPA activo (campo mandato_activo en clientes)",
        examples=[True]
    )


class EsgMonthlyReportOut(BaseModel):
    """Reporte ESG financiero del mes en curso."""

    periodo: str = Field(..., description="YYYY-MM")
    total_co2_kg: float = Field(..., ge=0, description="Suma mensual de huella (kg CO2)")
    total_portes: int = Field(..., ge=0, description="Cantidad de portes incluidos")


class CIPMatrixPoint(BaseModel):
    """
    Punto para Matriz CIP (Análisis Estratégico Margen vs. Emisiones).
    """

    ruta: str = Field(..., description='Ruta legible, ej. "Madrid - Barcelona"')
    margen_neto: float = Field(..., description="Margen neto total de la ruta (Ingresos - Costes)")
    emisiones_co2: float = Field(..., ge=0, description="Emisiones totales de CO2 (kg) en la ruta")
    total_portes: int = Field(..., ge=0, description="Número de portes agregados en la ruta")


class SimulationInput(BaseModel):
    """Parámetros de sensibilidad para el simulador económico."""

    cambio_combustible_pct: float = Field(
        default=0.0,
        ge=-100,
        le=500,
        description="Variación porcentual del coste de combustible",
        examples=[12.5],
    )
    cambio_salarios_pct: float = Field(
        default=0.0,
        ge=-100,
        le=500,
        description="Variación porcentual del coste de personal/salarios",
        examples=[5.0],
    )
    cambio_peajes_pct: float = Field(
        default=0.0,
        ge=-100,
        le=500,
        description="Variación porcentual del coste de peajes",
        examples=[8.0],
    )


class SimulationBreakEvenOut(BaseModel):
    tarifa_incremento_pct: float = Field(
        ...,
        description="Incremento porcentual medio de tarifas necesario para sostener el margen actual",
        examples=[4.2],
    )
    incremento_ingresos_eur: float = Field(
        ...,
        description="Incremento de ingresos agregado requerido para compensar el impacto simulado",
        examples=[6200.0],
    )


class SimulationResultOut(BaseModel):
    """Resultado del simulador de impacto económico (ventana 3 meses)."""

    periodo_meses: int = Field(default=3, description="Meses considerados en el cálculo", examples=[3])
    ingresos_base_eur: float = Field(..., description="Ingresos netos base (sin IVA)", examples=[148000.0])
    gastos_base_eur: float = Field(..., description="Gastos netos base (sin IVA)", examples=[112500.0])
    ebitda_base_eur: float = Field(..., description="EBITDA base del periodo", examples=[35500.0])
    ebitda_simulado_eur: float = Field(..., description="EBITDA tras aplicar la simulación", examples=[28900.0])
    impacto_ebitda_eur: float = Field(..., description="Impacto absoluto sobre EBITDA", examples=[-6600.0])
    impacto_ebitda_pct: float = Field(
        ...,
        description="Impacto relativo sobre EBITDA base (porcentaje)",
        examples=[-18.59],
    )
    impacto_mensual_estimado_eur: float = Field(
        ...,
        description="Impacto medio estimado por mes en el beneficio",
        examples=[-2200.0],
    )
    costes_categoria_base: dict[str, float] = Field(
        default_factory=dict,
        description="Coste base por categoría en el periodo (combustible, salarios, peajes)",
    )
    costes_categoria_simulada: dict[str, float] = Field(
        default_factory=dict,
        description="Coste simulado por categoría en el periodo",
    )
    break_even: SimulationBreakEvenOut
