from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.economic_insights import (
    AdvancedMetricsMonthRow,
    AdvancedMetricsOut,
    ClienteRentabilidadOut,
    EconomicInsightsOut,
    GastoCategoriaTreemapOut,
    MargenKmGasoilMensualOut,
    PuntoEquilibrioOut,
)
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

    @staticmethod
    def _fecha_desde_campo(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        s = str(val).strip()[:10]
        if len(s) >= 10 and s[4] == "-":
            try:
                return date.fromisoformat(s)
            except ValueError:
                return None
        return None

    @staticmethod
    def _es_gasto_fijo_heuristica(categoria: str | None) -> bool:
        """Sin columna explícita en BD: categorías típicas de estructura fija."""
        c = (categoria or "").lower()
        claves = (
            "seguro",
            "alquiler",
            "renting",
            "leasing",
            "oficina",
            "admin",
            "nomina",
            "nómina",
            "software",
            "licencia",
            "cuota fija",
            "comunidad",
            "sueldo",
        )
        return any(k in c for k in claves)

    async def economic_insights_advanced(
        self, *, empresa_id: str, hoy: date | None = None
    ) -> EconomicInsightsOut:
        """
        Vista económica avanzada (solo agregados; mismas reglas sin IVA que ``financial_dashboard``).

        Los datos sensibles en reposo (p. ej. IBAN cifrado) no se exponen: solo totales operativos
        vía tablas ``facturas``, ``gastos``, ``portes``, ``clientes``.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            ref = f"{date.today().year:04d}-{date.today().month:02d}"
            return EconomicInsightsOut(
                coste_medio_km_ultimos_30d=None,
                km_operativos_ultimos_30d=0.0,
                gastos_operativos_ultimos_30d=0.0,
                top_clientes_rentabilidad=[],
                ingresos_vs_gastos_mensual=[],
                margen_km_vs_gasoil_mensual=[],
                gastos_por_categoria=[],
                punto_equilibrio_mensual=PuntoEquilibrioOut(
                    periodo_referencia=ref,
                    gastos_fijos_mes_eur=0.0,
                    gastos_variables_mes_eur=0.0,
                    ingresos_mes_eur=0.0,
                ),
            )

        if hoy is None:
            hoy = date.today()

        d30 = hoy - timedelta(days=30)

        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select("base_imponible, total_factura, cuota_iva, fecha_emision, cliente, total_km_estimados_snapshot")
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []

        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []

        res_portes: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("portes")
                .select("km_estimados, fecha")
                .eq("empresa_id", eid)
            )
        )
        porte_rows: list[dict[str, Any]] = (res_portes.data or []) if hasattr(res_portes, "data") else []

        km_30 = 0.0
        for pr in porte_rows:
            fd = self._fecha_desde_campo(pr.get("fecha"))
            if fd is None or fd < d30 or fd > hoy:
                continue
            km_30 += float(pr.get("km_estimados") or 0.0)

        gas_30 = 0.0
        for r in gas_rows:
            fd = self._fecha_desde_campo(r.get("fecha"))
            if fd is None or fd < d30 or fd > hoy:
                continue
            gas_30 += self._gasto_neto_sin_iva(r)

        coste_km: float | None = None
        if km_30 > 1e-9:
            coste_km = round(gas_30 / km_30, 6)

        ing_por_cli: dict[str, float] = defaultdict(float)
        for r in fact_rows:
            cid = str(r.get("cliente") or "").strip()
            if not cid:
                continue
            ing_por_cli[cid] += self._ingreso_neto_sin_iva(r)

        total_ing = float(sum(ing_por_cli.values()))
        total_gastos_neto = float(sum(self._gasto_neto_sin_iva(r) for r in gas_rows))

        nombres: dict[str, str] = {}
        if ing_por_cli:
            try:
                rc: Any = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes")
                        .select("id, nombre")
                        .eq("empresa_id", eid)
                        .in_("id", list(ing_por_cli.keys()))
                    )
                )
                for crow in (rc.data or []) if hasattr(rc, "data") else []:
                    cid = str(crow.get("id") or "").strip()
                    if cid:
                        nombres[cid] = str(crow.get("nombre") or "").strip() or cid
            except Exception:
                pass

        ranking: list[ClienteRentabilidadOut] = []
        if total_ing > 1e-9 and total_gastos_neto >= 0:
            for cid, ing in ing_por_cli.items():
                if ing <= 0:
                    continue
                share = ing / total_ing
                gas_asig = total_gastos_neto * share
                margen_pct = ((ing - gas_asig) / ing) * 100.0 if ing > 0 else 0.0
                ranking.append(
                    ClienteRentabilidadOut(
                        cliente_id=cid,
                        cliente_nombre=nombres.get(cid, cid),
                        ingresos_netos_eur=round(ing, 2),
                        margen_pct=round(margen_pct, 2),
                        gasto_asignado_eur=round(gas_asig, 2),
                    )
                )
        ranking.sort(key=lambda x: (x.margen_pct, x.ingresos_netos_eur), reverse=True)
        top5 = ranking[:5]

        claves12 = self._ultimos_n_meses_clave(hoy=hoy, n=12)
        ing_mes12: dict[str, float] = {k: 0.0 for k in claves12}
        gas_mes12: dict[str, float] = {k: 0.0 for k in claves12}
        for r in fact_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha_emision"))
            if pk in ing_mes12:
                ing_mes12[pk] += self._ingreso_neto_sin_iva(r)
        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk in gas_mes12:
                gas_mes12[pk] += self._gasto_neto_sin_iva(r)

        serie12 = [
            FinanceMensualBarOut(periodo=k, ingresos=round(ing_mes12[k], 2), gastos=round(gas_mes12[k], 2))
            for k in claves12
        ]

        cat_tot: dict[str, float] = defaultdict(float)
        claves_set12 = set(claves12)
        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk not in claves_set12:
                continue
            cat = str(r.get("categoria") or "Sin categoría").strip() or "Sin categoría"
            cat_tot[cat] += self._gasto_neto_sin_iva(r)
        treemap = [
            GastoCategoriaTreemapOut(name=k, value=round(v, 2))
            for k, v in sorted(cat_tot.items(), key=lambda x: -x[1])
        ]

        def _margen_neto_km_mes(yyyy_mm: str) -> float | None:
            ing_m = 0.0
            gas_m = 0.0
            km_m = 0.0
            for r in fact_rows:
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

        def _combustible_mes(yyyy_mm: str) -> float:
            t = 0.0
            for r in gas_rows:
                if self._periodo_yyyy_mm(r.get("fecha")) != yyyy_mm:
                    continue
                if self._bucket_gasto_cinco(str(r.get("categoria") or "")) != "Combustible":
                    continue
                t += self._gasto_neto_sin_iva(r)
            return t

        def _km_fact_mes(yyyy_mm: str) -> float:
            tot = 0.0
            for r in fact_rows:
                if self._periodo_yyyy_mm(r.get("fecha_emision")) != yyyy_mm:
                    continue
                tot += float(r.get("total_km_estimados_snapshot") or 0.0)
            return tot

        mix: list[MargenKmGasoilMensualOut] = []
        for k in claves12:
            mk = _margen_neto_km_mes(k)
            kmk = _km_fact_mes(k)
            comb = _combustible_mes(k)
            cpk = round(comb / kmk, 6) if kmk > 1e-9 else None
            mix.append(
                MargenKmGasoilMensualOut(
                    periodo=k,
                    margen_neto_km_eur=mk,
                    coste_combustible_por_km_eur=cpk,
                )
            )

        cur_mes = f"{hoy.year:04d}-{hoy.month:02d}"
        ing_cur = 0.0
        gas_fijo_cur = 0.0
        gas_var_cur = 0.0
        for r in fact_rows:
            if self._periodo_yyyy_mm(r.get("fecha_emision")) != cur_mes:
                continue
            ing_cur += self._ingreso_neto_sin_iva(r)
        for r in gas_rows:
            if self._periodo_yyyy_mm(r.get("fecha")) != cur_mes:
                continue
            net = self._gasto_neto_sin_iva(r)
            if self._es_gasto_fijo_heuristica(str(r.get("categoria") or "")):
                gas_fijo_cur += net
            else:
                gas_var_cur += net

        mc_ratio: float | None = None
        if ing_cur > 1e-9:
            mc_ratio = round((ing_cur - gas_var_cur) / ing_cur, 6)
        ing_eq: float | None = None
        if mc_ratio is not None and mc_ratio > 1e-6 and gas_fijo_cur > 0:
            ing_eq = round(gas_fijo_cur / mc_ratio, 2)

        mk_cur = _margen_neto_km_mes(cur_mes)
        km_cur = _km_fact_mes(cur_mes)
        km_eq: float | None = None
        if mk_cur is not None and mk_cur > 1e-9 and gas_fijo_cur > 0:
            km_eq = round(gas_fijo_cur / mk_cur, 3)

        pe = PuntoEquilibrioOut(
            periodo_referencia=cur_mes,
            gastos_fijos_mes_eur=round(gas_fijo_cur, 2),
            gastos_variables_mes_eur=round(gas_var_cur, 2),
            ingresos_mes_eur=round(ing_cur, 2),
            margen_contribucion_ratio=mc_ratio,
            ingreso_equilibrio_estimado_eur=ing_eq,
            km_equilibrio_estimados=km_eq,
            nota_metodologia=(
                "Gastos fijos inferidos por palabras clave en categoría (seguros, alquiler, nóminas, etc.). "
                "Valide con su contabilidad."
            ),
        )

        return EconomicInsightsOut(
            coste_medio_km_ultimos_30d=coste_km,
            km_operativos_ultimos_30d=round(km_30, 3),
            gastos_operativos_ultimos_30d=round(gas_30, 2),
            top_clientes_rentabilidad=top5,
            ingresos_vs_gastos_mensual=serie12,
            margen_km_vs_gasoil_mensual=mix,
            gastos_por_categoria=treemap,
            punto_equilibrio_mensual=pe,
        )

    @staticmethod
    def _gasto_flota_peaje_combustible(row: dict[str, Any]) -> bool:
        """Gastos imputables a coste operativo por km: combustible, peajes, mantenimiento flota."""
        b = FinanceService._bucket_gasto_cinco(str(row.get("categoria") or ""))
        return b in ("Combustible", "Peajes", "Mantenimiento")

    async def advanced_metrics_last_six_months(
        self, *, empresa_id: str, hoy: date | None = None
    ) -> AdvancedMetricsOut:
        """
        Últimos 6 meses calendario: margen contribución, coste/km (flota+peaje+comb. / km portes),
        CO₂ (combustible Scope 1 + huella t·km en portes) y ratio ingresos/CO₂ (EBITDA verde).
        """
        from app.services.eco_service import EcoService, co2_emitido_desde_porte_row

        eid = str(empresa_id or "").strip()
        if not eid:
            return AdvancedMetricsOut(meses=[], generado_en=date.today().isoformat())

        if hoy is None:
            hoy = date.today()

        claves6 = self._ultimos_n_meses_clave(hoy=hoy, n=6)
        claves_set = set(claves6)

        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select("base_imponible, total_factura, cuota_iva, fecha_emision")
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []

        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []

        res_portes: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("portes")
                .select("km_estimados, fecha, peso_ton, bultos")
                .eq("empresa_id", eid)
            )
        )
        porte_rows: list[dict[str, Any]] = (res_portes.data or []) if hasattr(res_portes, "data") else []

        eco = EcoService(self._db)
        emis_mes = await eco.emisiones_combustible_por_mes(empresa_id=eid)
        co2_combustible: dict[str, float] = {e.periodo: float(e.co2_kg) for e in emis_mes}

        ing_m: dict[str, float] = {k: 0.0 for k in claves6}
        gas_op_m: dict[str, float] = {k: 0.0 for k in claves6}
        gas_km_m: dict[str, float] = {k: 0.0 for k in claves6}
        km_p: dict[str, float] = {k: 0.0 for k in claves6}
        co2_porte_m: dict[str, float] = {k: 0.0 for k in claves6}

        for r in fact_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha_emision"))
            if pk not in claves_set:
                continue
            ing_m[pk] += self._ingreso_neto_sin_iva(r)

        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk not in claves_set:
                continue
            neto = self._gasto_neto_sin_iva(r)
            gas_op_m[pk] += neto
            if self._gasto_flota_peaje_combustible(r):
                gas_km_m[pk] += neto

        for pr in porte_rows:
            fd = self._fecha_desde_campo(pr.get("fecha"))
            if fd is None:
                continue
            pk = f"{fd.year:04d}-{fd.month:02d}"
            if pk not in claves_set:
                continue
            km_p[pk] += float(pr.get("km_estimados") or 0.0)
            co2_porte_m[pk] += co2_emitido_desde_porte_row(pr)

        meses: list[AdvancedMetricsMonthRow] = []
        for pk in claves6:
            ing = round(ing_m.get(pk, 0.0), 2)
            gop = round(gas_op_m.get(pk, 0.0), 2)
            margen = round(ing - gop, 2)
            km = round(km_p.get(pk, 0.0), 3)
            g_km_num = round(gas_km_m.get(pk, 0.0), 2)
            coste_km = round(g_km_num / km, 6) if km > 1e-9 else None
            co2_cb = round(co2_combustible.get(pk, 0.0), 3)
            co2_pt = round(co2_porte_m.get(pk, 0.0), 3)
            co2_tot = round(co2_cb + co2_pt, 3)
            ratio = round(ing / co2_tot, 4) if co2_tot > 1e-9 else None
            meses.append(
                AdvancedMetricsMonthRow(
                    periodo=pk,
                    ingresos_facturacion_eur=ing,
                    gastos_operativos_eur=gop,
                    margen_contribucion_eur=margen,
                    km_portes=km,
                    gastos_flota_peaje_combustible_eur=g_km_num,
                    coste_por_km_eur=coste_km,
                    emisiones_co2_kg=co2_tot,
                    emisiones_co2_combustible_kg=co2_cb,
                    emisiones_co2_portes_kg=co2_pt,
                    ebitda_verde_eur_por_kg_co2=ratio,
                )
            )

        return AdvancedMetricsOut(
            meses=meses,
            generado_en=hoy.isoformat(),
            nota_metodologia=(
                "Ingresos y gastos sin IVA. Coste/km = (combustible + peajes + mantenimiento bucket) / km portes. "
                "CO₂ = Scope 1 combustible (tickets) + huella t·km portes."
            ),
        )
