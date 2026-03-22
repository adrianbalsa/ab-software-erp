from __future__ import annotations

from datetime import date
from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.finance import (
    FinanceDashboardOut,
    FinanceMensualBarOut,
    FinanceSummaryOut,
    FinanceTesoreriaMensualOut,
    GastoBucketCincoOut,
)


class FinanceService:
    """
    Inteligencia financiera (EBITDA operativo aproximado) por empresa vía `SupabaseAsync`.

    Criterio profesional **sin IVA**:
    - **Ingresos**: suma de `base_imponible` en **facturas emitidas** (reconocimiento de ingreso).
      Si falta la base, se usa `total_factura - cuota_iva`.
    - **Gastos**: importe del ticket (`total_eur` o `total_chf`) **menos** la cuota `iva`
      registrada cuando existe; si no hay desglose de IVA, se toma el importe como neto.
    - **EBITDA** ≈ ingresos netos (sin IVA) − gastos netos (sin IVA).
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    def obtener_categorias(self) -> list[str]:
        return [
            "Material",
            "Combustible",
            "Dietas",
            "Herramienta",
            "Vehículo Mantenimiento",
            "Oficina/Admin",
            "Seguros",
            "Otros",
        ]

    @staticmethod
    def _ingreso_neto_sin_iva(row: dict[str, Any]) -> float:
        """Factura: ingreso operativo sin IVA."""
        base = row.get("base_imponible")
        if base is not None:
            return float(base)

        total = float(row.get("total_factura") or 0.0)
        cuota = float(row.get("cuota_iva") or 0.0)
        return max(0.0, total - cuota)

    @staticmethod
    def _gasto_neto_sin_iva(row: dict[str, Any]) -> float:
        """
        Gasto: importe total del documento menos cuota de IVA si consta.

        Se asume que `total_eur` / `total_chf` es el total del ticket (habitualmente
        con IVA incluido) y `iva` la parte impositiva en EUR; si `iva` no viene
        informada, no se resta nada (se interpreta como importe ya neto o sin desglose).
        """
        te = row.get("total_eur")
        gross = float(te) if te is not None else float(row.get("total_chf") or 0.0)

        iva_raw = row.get("iva")
        if iva_raw is None:
            return max(0.0, gross)
        try:
            iva_part = float(iva_raw)
        except (TypeError, ValueError):
            return max(0.0, gross)
        if iva_part <= 0:
            return max(0.0, gross)
        return max(0.0, gross - iva_part)

    @staticmethod
    def _periodo_yyyy_mm(val: Any) -> str | None:
        if val is None:
            return None
        s = str(val).strip()
        if len(s) >= 7 and s[4] == "-" and s[6:7] != "":
            return s[:7]
        return None

    @staticmethod
    def _mes_anterior_clave(hoy: date) -> str:
        y, m = hoy.year, hoy.month
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        return f"{y:04d}-{m:02d}"

    @staticmethod
    def _bucket_gasto_cinco(categoria: str | None) -> str:
        """
        Mapea categoría de ticket a 5 buckets UI: Combustible, Personal,
        Mantenimiento, Seguros, Peajes (resto → Mantenimiento).
        """
        c = (categoria or "").strip().lower()
        if "combust" in c:
            return "Combustible"
        if "seguro" in c:
            return "Seguros"
        if "peaje" in c:
            return "Peajes"
        if "dieta" in c or "nómina" in c or "nomina" in c or "personal" in c:
            return "Personal"
        if "oficina" in c or "admin" in c:
            return "Personal"
        if "manten" in c or "herramient" in c or "material" in c or "vehículo" in c or "vehiculo" in c:
            return "Mantenimiento"
        if c in ("", "otros"):
            return "Mantenimiento"
        return "Mantenimiento"

    @staticmethod
    def _ultimos_n_meses_clave(*, hoy: date, n: int) -> list[str]:
        """Claves YYYY-MM de los últimos ``n`` meses incluyendo el mes actual (orden cronológico)."""
        y, m = hoy.year, hoy.month
        out: list[str] = []
        for _ in range(n):
            out.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        out.reverse()
        return out

    async def financial_summary(self, *, empresa_id: str) -> FinanceSummaryOut:
        """
        EBITDA operativo (aprox.) **excluyendo IVA** en ingresos y gastos.

        Todas las lecturas pasan por `SupabaseAsync.execute` sobre tablas `facturas` y `gastos`,
        filtradas por `empresa_id`.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return FinanceSummaryOut(ingresos=0.0, gastos=0.0, ebitda=0.0)

        # 1. INGRESOS: facturas emitidas (base neta sin IVA)
        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select("base_imponible, total_factura, cuota_iva")
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []
        ingresos = float(sum(self._ingreso_neto_sin_iva(r) for r in fact_rows))

        # 2. GASTOS: tickets activos; restar IVA del ticket cuando consta
        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (
            (res_gas.data or []) if hasattr(res_gas, "data") else []
        )
        gastos = float(sum(self._gasto_neto_sin_iva(r) for r in gas_rows))

        ebitda = ingresos - gastos

        return FinanceSummaryOut(ingresos=ingresos, gastos=gastos, ebitda=ebitda)

    async def financial_dashboard(self, *, empresa_id: str, hoy: date | None = None) -> FinanceDashboardOut:
        """
        KPIs como ``financial_summary`` más ``total_km_estimados_snapshot`` (suma en facturas),
        ``margen_km_eur`` y serie de 6 meses (ingresos por ``fecha_emision`` de facturas).
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return FinanceDashboardOut(
                ingresos=0.0,
                gastos=0.0,
                ebitda=0.0,
                total_km_estimados_snapshot=0.0,
                margen_km_eur=None,
                ingresos_vs_gastos_mensual=[],
                tesoreria_mensual=[],
                gastos_por_bucket_cinco=[],
                margen_neto_km_mes_actual=None,
                margen_neto_km_mes_anterior=None,
                variacion_margen_km_pct=None,
                km_facturados_mes_actual=None,
                km_facturados_mes_anterior=None,
            )

        if hoy is None:
            hoy = date.today()

        summary = await self.financial_summary(empresa_id=eid)

        res_fac_full: Any = await self._db.execute(
            self._db.table("facturas")
            .select(
                "base_imponible, total_factura, cuota_iva, fecha_emision, "
                "total_km_estimados_snapshot, estado_cobro"
            )
            .eq("empresa_id", eid)
        )
        fact_rows_full: list[dict[str, Any]] = (
            (res_fac_full.data or []) if hasattr(res_fac_full, "data") else []
        )
        total_km = float(
            sum(float(r.get("total_km_estimados_snapshot") or 0.0) for r in fact_rows_full)
        )
        margen_km: float | None = None
        if total_km > 0:
            margen_km = float(summary.ebitda) / total_km

        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []

        claves = self._ultimos_n_meses_clave(hoy=hoy, n=6)
        ing_mes: dict[str, float] = {k: 0.0 for k in claves}
        gas_mes: dict[str, float] = {k: 0.0 for k in claves}

        for r in fact_rows_full:
            pk = self._periodo_yyyy_mm(r.get("fecha_emision"))
            if pk in ing_mes:
                ing_mes[pk] += self._ingreso_neto_sin_iva(r)

        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk in gas_mes:
                gas_mes[pk] += self._gasto_neto_sin_iva(r)

        serie = [
            FinanceMensualBarOut(periodo=k, ingresos=round(ing_mes[k], 2), gastos=round(gas_mes[k], 2))
            for k in claves
        ]

        claves_set = set(claves)

        def _es_cobrada(row: dict[str, Any]) -> bool:
            return str(row.get("estado_cobro") or "").strip().lower() == "cobrada"

        tesoreria: list[FinanceTesoreriaMensualOut] = []
        for k in claves:
            ing_f = 0.0
            cob = 0.0
            for r in fact_rows_full:
                pk = self._periodo_yyyy_mm(r.get("fecha_emision"))
                if pk != k:
                    continue
                net = self._ingreso_neto_sin_iva(r)
                ing_f += net
                if _es_cobrada(r):
                    cob += net
            tesoreria.append(
                FinanceTesoreriaMensualOut(
                    periodo=k,
                    ingresos_facturados=round(max(0.0, ing_f), 2),
                    cobros_reales=round(max(0.0, cob), 2),
                )
            )

        bucket_totals: dict[str, float] = {
            "Combustible": 0.0,
            "Personal": 0.0,
            "Mantenimiento": 0.0,
            "Seguros": 0.0,
            "Peajes": 0.0,
        }
        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk not in claves_set:
                continue
            b = self._bucket_gasto_cinco(str(r.get("categoria") or ""))
            bucket_totals[b] = bucket_totals.get(b, 0.0) + self._gasto_neto_sin_iva(r)

        gastos_buckets = [
            GastoBucketCincoOut(name=name, value=round(v, 2))
            for name, v in bucket_totals.items()
        ]

        def _margen_neto_km_mes(yyyy_mm: str) -> float | None:
            ing_m = 0.0
            gas_m = 0.0
            km_m = 0.0
            for r in fact_rows_full:
                if self._periodo_yyyy_mm(r.get("fecha_emision")) != yyyy_mm:
                    continue
                ing_m += self._ingreso_neto_sin_iva(r)
                km_m += float(r.get("total_km_estimados_snapshot") or 0.0)
            for r in gas_rows:
                if self._periodo_yyyy_mm(r.get("fecha")) != yyyy_mm:
                    continue
                gas_m += self._gasto_neto_sin_iva(r)
            if km_m <= 0:
                return None
            return round((ing_m - gas_m) / km_m, 6)

        cur_mes = f"{hoy.year:04d}-{hoy.month:02d}"
        prev_mes = self._mes_anterior_clave(hoy)
        margen_act = _margen_neto_km_mes(cur_mes)
        margen_prev = _margen_neto_km_mes(prev_mes)

        var_pct: float | None = None
        if margen_act is not None and margen_prev is not None:
            if abs(margen_prev) < 1e-9:
                var_pct = None if abs(margen_act) < 1e-9 else 100.0
            else:
                var_pct = round((margen_act - margen_prev) / abs(margen_prev) * 100.0, 2)

        def _km_facturados_mes(yyyy_mm: str) -> float:
            tot = 0.0
            for r in fact_rows_full:
                if self._periodo_yyyy_mm(r.get("fecha_emision")) != yyyy_mm:
                    continue
                tot += float(r.get("total_km_estimados_snapshot") or 0.0)
            return round(tot, 3)

        km_cur = _km_facturados_mes(cur_mes)
        km_prev = _km_facturados_mes(prev_mes)

        return FinanceDashboardOut(
            ingresos=summary.ingresos,
            gastos=summary.gastos,
            ebitda=summary.ebitda,
            total_km_estimados_snapshot=round(total_km, 3),
            margen_km_eur=round(margen_km, 6) if margen_km is not None else None,
            ingresos_vs_gastos_mensual=serie,
            tesoreria_mensual=tesoreria,
            gastos_por_bucket_cinco=gastos_buckets,
            margen_neto_km_mes_actual=margen_act,
            margen_neto_km_mes_anterior=margen_prev,
            variacion_margen_km_pct=var_pct,
            km_facturados_mes_actual=km_cur if km_cur > 0 else None,
            km_facturados_mes_anterior=km_prev if km_prev > 0 else None,
        )
