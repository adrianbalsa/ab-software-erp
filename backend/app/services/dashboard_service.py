from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN
from typing import Any

from app.core.fiscal_logic import round_fiat, to_decimal
from app.core.math_engine import (
    FinancialDomainError,
    aggregate_portes_km_bultos,
    as_float_fiat,
    quantize_operational_km,
)
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.dashboard import DashboardStatsOut


@dataclass(frozen=True, slots=True)
class _MonthRange:
    start: date
    next_start: date


def _month_range(today: date) -> _MonthRange:
    start = date(today.year, today.month, 1)
    if today.month == 12:
        next_start = date(today.year + 1, 1, 1)
    else:
        next_start = date(today.year, today.month + 1, 1)
    return _MonthRange(start=start, next_start=next_start)


class DashboardService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def stats(self, *, empresa_id: str) -> DashboardStatsOut:
        """
        KPIs financieros + operativos del mes calendario actual (límites según ``CURRENT_DATE`` en
        ``vw_dashboard_summary``). Agregación en una sola lectura a la vista (sin N+1 en la app).
        """
        res: Any = await self._db.execute(
            self._db.table("vw_dashboard_summary")
            .select("ingresos_total,gastos_total,pendientes_cobro,km_totales_mes,bultos_mes")
            .eq("empresa_id", empresa_id)
            .limit(1)
        )
        raw = res.data if hasattr(res, "data") else None
        row: dict[str, Any]
        if isinstance(raw, list):
            row = raw[0] if raw else {}
        elif isinstance(raw, dict):
            row = raw
        else:
            row = {}

        # Motor fiat: sin float intermedio en EBITDA ni importes; serialización vía as_float_fiat.
        ing = round_fiat(to_decimal(row.get("ingresos_total")))
        gas = round_fiat(to_decimal(row.get("gastos_total")))
        ebitda_dec = round_fiat(ing - gas)
        pend_dec = round_fiat(to_decimal(row.get("pendientes_cobro")))
        km_dec = quantize_operational_km(to_decimal(row.get("km_totales_mes")))
        bultos_raw = row.get("bultos_mes")
        try:
            bultos_mes = int(
                to_decimal(0 if bultos_raw is None else bultos_raw).to_integral_value(rounding=ROUND_HALF_EVEN)
            )
        except (FinancialDomainError, ValueError, TypeError, ArithmeticError):
            bultos_mes = 0

        return DashboardStatsOut(
            ebitda_estimado=as_float_fiat(ebitda_dec),
            pendientes_cobro=as_float_fiat(pend_dec),
            km_totales_mes=float(km_dec),
            bultos_mes=bultos_mes,
        )

    async def stats_operativos_sin_finanzas(
        self,
        *,
        empresa_id: str,
        today: date | None = None,
    ) -> DashboardStatsOut:
        """
        KPIs operativos del mes (km / bultos) a nivel **empresa** (owner no usa este método;
        traffic_manager sí). Sin consultar facturas, gastos ni importes de portes.
        """
        if today is None:
            today = date.today()
        m = _month_range(today)
        res_mes: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("portes")
                .select("km_estimados, bultos")
                .eq("empresa_id", empresa_id)
                .gte("fecha", m.start.isoformat())
                .lt("fecha", m.next_start.isoformat())
            )
        )
        mes_rows: list[dict[str, Any]] = (res_mes.data or []) if hasattr(res_mes, "data") else []
        km_dec, bultos_mes = aggregate_portes_km_bultos(mes_rows)
        return DashboardStatsOut(
            ebitda_estimado=0.0,
            pendientes_cobro=0.0,
            km_totales_mes=float(km_dec),
            bultos_mes=bultos_mes,
        )

    async def stats_operativos_conductor(
        self,
        *,
        empresa_id: str,
        vehiculo_id: str,
        today: date | None = None,
    ) -> DashboardStatsOut:
        """
        KPIs operativos del mes **solo** para portes del vehículo indicado (rol driver).
        Defensa en profundidad: ``vehiculo_id`` vacío → ceros sin consulta agregada global.
        """
        v = (vehiculo_id or "").strip()
        if not v:
            return DashboardStatsOut(
                ebitda_estimado=0.0,
                pendientes_cobro=0.0,
                km_totales_mes=0.0,
                bultos_mes=0,
            )
        if today is None:
            today = date.today()
        m = _month_range(today)
        res_mes: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("portes")
                .select("km_estimados, bultos")
                .eq("empresa_id", empresa_id)
                .eq("vehiculo_id", v)
                .gte("fecha", m.start.isoformat())
                .lt("fecha", m.next_start.isoformat())
            )
        )
        mes_rows: list[dict[str, Any]] = (res_mes.data or []) if hasattr(res_mes, "data") else []
        km_dec, bultos_mes = aggregate_portes_km_bultos(mes_rows)
        return DashboardStatsOut(
            ebitda_estimado=0.0,
            pendientes_cobro=0.0,
            km_totales_mes=float(km_dec),
            bultos_mes=bultos_mes,
        )

