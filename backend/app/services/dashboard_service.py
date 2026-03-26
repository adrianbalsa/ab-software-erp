from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

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

    async def stats(self, *, empresa_id: str, today: date | None = None) -> DashboardStatsOut:
        if today is None:
            today = date.today()
        m = _month_range(today)

        # Ingresos: sum(total_factura)
        res_fact: Any = await self._db.execute(
            self._db.table("facturas").select("total_factura").eq("empresa_id", empresa_id)
        )
        fact_rows: list[dict[str, Any]] = (res_fact.data or []) if hasattr(res_fact, "data") else []
        ingresos = float(sum(float(r.get("total_factura") or 0.0) for r in fact_rows))

        # Gastos: preferir total_eur, fallback total_chf (misma lógica que FinanceService)
        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", empresa_id))
        )
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []

        def _monto(r: dict[str, Any]) -> float:
            te = r.get("total_eur")
            if te is not None:
                return float(te)
            return float(r.get("total_chf") or 0.0)

        gastos_total = float(sum(_monto(r) for r in gas_rows))

        ebitda = ingresos - gastos_total

        # Pendientes de cobro: sum(precio_pactado) where estado='pendiente'
        res_pend: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("portes")
                .select("precio_pactado")
                .eq("empresa_id", empresa_id)
                .eq("estado", "pendiente")
            )
        )
        pend_rows: list[dict[str, Any]] = (res_pend.data or []) if hasattr(res_pend, "data") else []
        pendientes_cobro = float(sum(float(r.get("precio_pactado") or 0.0) for r in pend_rows))

        # Métricas mes: km_estimados + bultos
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
        km_mes = float(sum(float(r.get("km_estimados") or 0.0) for r in mes_rows))
        bultos_mes = int(sum(int(r.get("bultos") or 0) for r in mes_rows))

        return DashboardStatsOut(
            ebitda_estimado=ebitda,
            pendientes_cobro=pendientes_cobro,
            km_totales_mes=km_mes,
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
        km_mes = float(sum(float(r.get("km_estimados") or 0.0) for r in mes_rows))
        bultos_mes = int(sum(int(r.get("bultos") or 0) for r in mes_rows))
        return DashboardStatsOut(
            ebitda_estimado=0.0,
            pendientes_cobro=0.0,
            km_totales_mes=km_mes,
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
        km_mes = float(sum(float(r.get("km_estimados") or 0.0) for r in mes_rows))
        bultos_mes = int(sum(int(r.get("bultos") or 0) for r in mes_rows))
        return DashboardStatsOut(
            ebitda_estimado=0.0,
            pendientes_cobro=0.0,
            km_totales_mes=km_mes,
            bultos_mes=bultos_mes,
        )

