from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from decimal import Decimal

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.core.math_engine import quantize_currency, to_decimal
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
    def _decimal_or_zero(value: Any) -> Decimal:
        """Normaliza nulos a Decimal('0.00') y evita errores en sumas."""
        try:
            return to_decimal(value)
        except Exception:
            return Decimal("0.00")

    @staticmethod
    def _ingreso_neto_sin_iva(row: dict[str, Any]) -> Decimal:
        """Factura: ingreso operativo sin IVA."""
        base = row.get("base_imponible")
        if base is not None:
            return quantize_currency(FinanceService._decimal_or_zero(base))

        total = FinanceService._decimal_or_zero(row.get("total_factura"))
        cuota = FinanceService._decimal_or_zero(row.get("cuota_iva"))
        net = total - cuota
        if net < 0:
            net = Decimal("0.00")
        return quantize_currency(net)

    @staticmethod
    def _gasto_neto_sin_iva(row: dict[str, Any]) -> Decimal:
        """
        Gasto: importe total del documento menos cuota de IVA si consta.

        Se asume que `total_eur` / `total_chf` es el total del ticket (habitualmente
        con IVA incluido) y `iva` la parte impositiva en EUR; si `iva` no viene
        informada, no se resta nada (se interpreta como importe ya neto o sin desglose).
        """
        te = row.get("total_eur")
        gross = FinanceService._decimal_or_zero(te if te is not None else row.get("total_chf"))

        iva_raw = row.get("iva")
        if iva_raw is None:
            net = gross
        else:
            iva_part = FinanceService._decimal_or_zero(iva_raw)
            if iva_part <= 0:
                net = gross
            else:
                net = gross - iva_part
        if net < 0:
            net = Decimal("0.00")
        return quantize_currency(net)

    @staticmethod
    def _recalculate_ebitda_and_margen_km(
        *,
        ingresos: Decimal,
        gastos: Decimal,
        km_facturados: Decimal,
    ) -> tuple[Decimal, Decimal | None]:
        """
        Recalcula EBITDA y margen por KM con redondeo monetario.
        Margen_km = (Ingresos - Gastos) / KM facturados.
        """
        ingresos_q = quantize_currency(ingresos)
        gastos_q = quantize_currency(gastos)
        ebitda = quantize_currency(ingresos_q - gastos_q)
        if km_facturados <= 0:
            return ebitda, None
        margen = quantize_currency(ebitda / km_facturados)
        return ebitda, margen

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
    def _mes_actual_clave(hoy: date) -> str:
        return f"{hoy.year:04d}-{hoy.month:02d}"

    @staticmethod
    def _period_month_or_current(value: str | None, *, hoy: date) -> str:
        raw = str(value or "").strip()
        if len(raw) == 7 and raw[4] == "-" and raw[:4].isdigit() and raw[5:7].isdigit():
            mm = int(raw[5:7])
            if 1 <= mm <= 12:
                return raw
        return FinanceService._mes_actual_clave(hoy)

    async def _snapshot_kpis_mes(
        self,
        *,
        empresa_id: str,
        period_month: str,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Lee KPIs preagregados desde `finance_kpi_snapshots` (O(1)).
        Si no existe snapshot para el mes solicitado, retorna ceros.
        """
        res: Any = await self._db.execute(
            self._db.table("finance_kpi_snapshots")
            .select("ingresos_operacion, gastos_operacion, ebitda")
            .eq("empresa_id", empresa_id)
            .eq("period_month", period_month)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
        row = rows[0]
        ingresos = quantize_currency(self._decimal_or_zero(row.get("ingresos_operacion")))
        gastos = quantize_currency(self._decimal_or_zero(row.get("gastos_operacion")))
        ebitda = quantize_currency(self._decimal_or_zero(row.get("ebitda")))
        return ingresos, gastos, ebitda

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

    async def financial_summary(self, *, empresa_id: str, period_month: str | None = None) -> FinanceSummaryOut:
        """
        KPIs financieros del mes actual desde snapshot preagregado (`finance_kpi_snapshots`).
        Fallback a 0 cuando aún no existe snapshot del periodo.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return FinanceSummaryOut(ingresos=0.0, gastos=0.0, ebitda=0.0)
        period_month = self._period_month_or_current(period_month, hoy=date.today())
        ingresos, gastos, ebitda = await self._snapshot_kpis_mes(
            empresa_id=eid,
            period_month=period_month,
        )
        return FinanceSummaryOut(
            ingresos=float(ingresos),
            gastos=float(gastos),
            ebitda=float(ebitda),
        )

    async def financial_dashboard(
        self,
        *,
        empresa_id: str,
        hoy: date | None = None,
        period_month: str | None = None,
    ) -> FinanceDashboardOut:
        """
        Dashboard financiero optimizado para O(1): consume snapshot mensual preagregado.
        Fallback a cero si el snapshot del mes actual no existe.
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
        period_month = self._period_month_or_current(period_month, hoy=hoy)
        ingresos, gastos, ebitda = await self._snapshot_kpis_mes(
            empresa_id=eid,
            period_month=period_month,
        )

        return FinanceDashboardOut(
            ingresos=float(ingresos),
            gastos=float(gastos),
            ebitda=float(ebitda),
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

        km_30 = Decimal("0.00")
        for pr in porte_rows:
            fd = self._fecha_desde_campo(pr.get("fecha"))
            if fd is None or fd < d30 or fd > hoy:
                continue
            km_30 += self._decimal_or_zero(pr.get("km_estimados"))

        gas_30 = Decimal("0.00")
        for r in gas_rows:
            fd = self._fecha_desde_campo(r.get("fecha"))
            if fd is None or fd < d30 or fd > hoy:
                continue
            gas_30 += self._gasto_neto_sin_iva(r)

        coste_km: float | None = None
        if km_30 > 0:
            coste_km = float(quantize_currency(gas_30 / km_30))

        ing_por_cli: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for r in fact_rows:
            cid = str(r.get("cliente") or "").strip()
            if not cid:
                continue
            ing_por_cli[cid] += self._ingreso_neto_sin_iva(r)

        total_ing = sum(ing_por_cli.values())
        total_gastos_neto = sum(self._gasto_neto_sin_iva(r) for r in gas_rows)

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
        if total_ing > 0 and total_gastos_neto >= 0:
            for cid, ing in ing_por_cli.items():
                if ing <= 0:
                    continue
                share = ing / total_ing
                gas_asig = total_gastos_neto * share
                margen_pct = ((ing - gas_asig) / ing) * Decimal("100") if ing > 0 else Decimal("0.00")
                ranking.append(
                    ClienteRentabilidadOut(
                        cliente_id=cid,
                        cliente_nombre=nombres.get(cid, cid),
                        ingresos_netos_eur=float(quantize_currency(ing)),
                        margen_pct=round(float(margen_pct), 2),
                        gasto_asignado_eur=float(quantize_currency(gas_asig)),
                    )
                )
        ranking.sort(key=lambda x: (x.margen_pct, x.ingresos_netos_eur), reverse=True)
        top5 = ranking[:5]

        claves12 = self._ultimos_n_meses_clave(hoy=hoy, n=12)
        ing_mes12: dict[str, Decimal] = {k: Decimal("0.00") for k in claves12}
        gas_mes12: dict[str, Decimal] = {k: Decimal("0.00") for k in claves12}
        for r in fact_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha_emision"))
            if pk in ing_mes12:
                ing_mes12[pk] += self._ingreso_neto_sin_iva(r)
        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk in gas_mes12:
                gas_mes12[pk] += self._gasto_neto_sin_iva(r)

        serie12 = [
            FinanceMensualBarOut(
                periodo=k,
                ingresos=float(quantize_currency(ing_mes12[k])),
                gastos=float(quantize_currency(gas_mes12[k])),
            )
            for k in claves12
        ]

        cat_tot: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        claves_set12 = set(claves12)
        for r in gas_rows:
            pk = self._periodo_yyyy_mm(r.get("fecha"))
            if pk not in claves_set12:
                continue
            cat = str(r.get("categoria") or "Sin categoría").strip() or "Sin categoría"
            cat_tot[cat] += self._gasto_neto_sin_iva(r)
        treemap = [
            GastoCategoriaTreemapOut(name=k, value=float(quantize_currency(v)))
            for k, v in sorted(cat_tot.items(), key=lambda x: -x[1])
        ]

        def _margen_neto_km_mes(yyyy_mm: str) -> Decimal | None:
            ing_m = Decimal("0.00")
            gas_m = Decimal("0.00")
            km_m = Decimal("0.00")
            for r in fact_rows:
                if self._periodo_yyyy_mm(r.get("fecha_emision")) != yyyy_mm:
                    continue
                ing_m += self._ingreso_neto_sin_iva(r)
                km_m += self._decimal_or_zero(r.get("total_km_estimados_snapshot"))
            for r in gas_rows:
                if self._periodo_yyyy_mm(r.get("fecha")) != yyyy_mm:
                    continue
                gas_m += self._gasto_neto_sin_iva(r)
            _, margen = self._recalculate_ebitda_and_margen_km(
                ingresos=ing_m,
                gastos=gas_m,
                km_facturados=km_m,
            )
            return margen

        def _combustible_mes(yyyy_mm: str) -> Decimal:
            t = Decimal("0.00")
            for r in gas_rows:
                if self._periodo_yyyy_mm(r.get("fecha")) != yyyy_mm:
                    continue
                if self._bucket_gasto_cinco(str(r.get("categoria") or "")) != "Combustible":
                    continue
                t += self._gasto_neto_sin_iva(r)
            return t

        def _km_fact_mes(yyyy_mm: str) -> Decimal:
            tot = Decimal("0.00")
            for r in fact_rows:
                if self._periodo_yyyy_mm(r.get("fecha_emision")) != yyyy_mm:
                    continue
                tot += self._decimal_or_zero(r.get("total_km_estimados_snapshot"))
            return tot

        mix: list[MargenKmGasoilMensualOut] = []
        for k in claves12:
            mk = _margen_neto_km_mes(k)
            kmk = _km_fact_mes(k)
            comb = _combustible_mes(k)
            cpk = float(quantize_currency(comb / kmk)) if kmk > 0 else None
            mix.append(
                MargenKmGasoilMensualOut(
                    periodo=k,
                    margen_neto_km_eur=float(mk) if mk is not None else None,
                    coste_combustible_por_km_eur=cpk,
                )
            )

        cur_mes = f"{hoy.year:04d}-{hoy.month:02d}"
        ing_cur = Decimal("0.00")
        gas_fijo_cur = Decimal("0.00")
        gas_var_cur = Decimal("0.00")
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
        if ing_cur > 0:
            mc_ratio = round(float((ing_cur - gas_var_cur) / ing_cur), 6)
        ing_eq: float | None = None
        if mc_ratio is not None and mc_ratio > 1e-6 and gas_fijo_cur > 0:
            ing_eq = float(quantize_currency(gas_fijo_cur / Decimal(str(mc_ratio))))

        mk_cur = _margen_neto_km_mes(cur_mes)
        km_cur = _km_fact_mes(cur_mes)
        km_eq: float | None = None
        if mk_cur is not None and mk_cur > 0 and gas_fijo_cur > 0:
            km_eq = round(float(gas_fijo_cur / mk_cur), 3)

        pe = PuntoEquilibrioOut(
            periodo_referencia=cur_mes,
            gastos_fijos_mes_eur=float(quantize_currency(gas_fijo_cur)),
            gastos_variables_mes_eur=float(quantize_currency(gas_var_cur)),
            ingresos_mes_eur=float(quantize_currency(ing_cur)),
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
            km_operativos_ultimos_30d=round(float(km_30), 3),
            gastos_operativos_ultimos_30d=float(quantize_currency(gas_30)),
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

        ing_m: dict[str, Decimal] = {k: Decimal("0.00") for k in claves6}
        gas_op_m: dict[str, Decimal] = {k: Decimal("0.00") for k in claves6}
        gas_km_m: dict[str, Decimal] = {k: Decimal("0.00") for k in claves6}
        km_p: dict[str, Decimal] = {k: Decimal("0.00") for k in claves6}
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
            km_p[pk] += self._decimal_or_zero(pr.get("km_estimados"))
            co2_porte_m[pk] += co2_emitido_desde_porte_row(pr)

        meses: list[AdvancedMetricsMonthRow] = []
        for pk in claves6:
            ing = quantize_currency(ing_m.get(pk, Decimal("0.00")))
            gop = quantize_currency(gas_op_m.get(pk, Decimal("0.00")))
            margen = quantize_currency(ing - gop)
            km = round(float(km_p.get(pk, Decimal("0.00"))), 3)
            g_km_num = quantize_currency(gas_km_m.get(pk, Decimal("0.00")))
            coste_km = float(quantize_currency(g_km_num / Decimal(str(km)))) if km > 0 else None
            co2_cb = round(co2_combustible.get(pk, 0.0), 3)
            co2_pt = round(co2_porte_m.get(pk, 0.0), 3)
            co2_tot = round(co2_cb + co2_pt, 3)
            ratio = round(float(ing) / co2_tot, 4) if co2_tot > 1e-9 else None
            meses.append(
                AdvancedMetricsMonthRow(
                    periodo=pk,
                    ingresos_facturacion_eur=float(ing),
                    gastos_operativos_eur=float(gop),
                    margen_contribucion_eur=float(margen),
                    km_portes=km,
                    gastos_flota_peaje_combustible_eur=float(g_km_num),
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
