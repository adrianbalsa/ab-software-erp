from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class WaterfallMesOut(BaseModel):
    """Cascada de liquidez del mes en curso (movimientos bancarios conciliados)."""

    saldo_inicial: float = Field(..., description="Suma conciliada con fecha anterior al mes")
    entradas_cobros: float = Field(..., description="Importes positivos conciliados en el mes")
    salidas_pagos: float = Field(..., description="Magnitud de importes negativos conciliados en el mes")
    saldo_final: float = Field(..., description="Suma conciliada hasta fin de mes (fiat)")
    mes_label: str = Field(..., description="YYYY-MM del mes de referencia")


class CashFlowOut(BaseModel):
    saldo_actual_estimado: float = Field(
        ...,
        description="Suma neta de importes en movimientos_bancarios con estado Conciliado",
    )
    cuentas_por_cobrar: float = Field(
        ...,
        description="Suma total_factura donde estado_cobro no es cobrada (equivalente a no Pagada)",
    )
    cuentas_por_pagar: float = Field(
        ...,
        description="Gastos con estado_pago pendiente (total EUR del ticket)",
    )
    ar_vencimiento_30d: float = Field(
        ...,
        description="Subconjunto de AR con vencimiento estimado dentro de los próximos 30 días",
    )
    ap_vencimiento_30d: float = Field(
        ...,
        description="Subconjunto de AP pendiente con vencimiento estimado dentro de los próximos 30 días",
    )
    proyeccion_30_dias: float = Field(
        ...,
        description="saldo_actual_estimado + ar_vencimiento_30d - ap_vencimiento_30d (fiat)",
    )
    waterfall_mes: WaterfallMesOut


class TreasuryArBucketOut(BaseModel):
    """Cubo de cuentas por cobrar según fecha estimada de cobro."""

    clave: str = Field(
        ...,
        description="vencido | proximos_7 | dias_8_15 | mas_15",
    )
    etiqueta: str = Field(..., description="Etiqueta para UI")
    importe: float = Field(..., description="Suma total_factura (fiat)")


class TreasuryProjectionOut(BaseModel):
    """
    Proyección de cobros pendientes por cubos y PMC (periodo medio de cobro) histórico.
    """

    fecha_referencia: date
    saldo_en_caja: float = Field(
        ...,
        description="Saldo neto movimientos bancarios conciliados (misma lógica que cash-flow)",
    )
    total_pendiente_cobro: float = Field(
        ...,
        description="Suma facturas con estado distinto de cobrada",
    )
    buckets: list[TreasuryArBucketOut]
    pmc_dias: float | None = Field(
        default=None,
        description="Media días entre fecha_emision y fecha_cobro_real (facturas cobradas con ambas fechas)",
    )
    pmc_muestras: int = Field(
        default=0,
        description="Número de facturas cobradas usadas para PMC global",
    )
    pmc_periodo_reciente_dias: float | None = Field(
        default=None,
        description="PMC medio en cobros con fecha_cobro_real en los últimos 90 días",
    )
    pmc_periodo_anterior_dias: float | None = Field(
        default=None,
        description="PMC medio en cobros con fecha_cobro_real entre 180 y 90 días atrás",
    )
    pmc_tendencia: Literal["mejorando", "empeorando", "estable"] = Field(
        default="estable",
        description="Comparación reciente vs periodo anterior (menor PMC = mejor)",
    )
