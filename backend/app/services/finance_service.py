from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db.session import get_session_factory
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.core.math_engine import quantize_currency, to_decimal
from app.services import finance_transactional_kpis as ftk
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
    GastoBucketMensualOut,
)
from app.core.constants import COSTE_OPERATIVO_EUR_KM
from app.services.audit_logs_service import AuditLogsService
from app.services.auditoria_service import AuditoriaService
from app.services.eco_service import EUR_POR_LITRO_DIESEL_REF, KG_CO2_POR_LITRO_DIESEL
# Opex no combustible (€/km) cuando sí hay reparto de combustible real (neumáticos, estructura, etc.).
OTHER_NON_FUEL_OPEX_PER_KM: float = float(os.getenv("OTHER_NON_FUEL_OPEX_PER_KM", "0.35"))


@dataclass(frozen=True, slots=True)
class PorteFuelAllocation:
    """Resultado de imputar ``gastos_vehiculo`` (combustible) a un porte."""

    porte_id: str
    fecha: date
    km: float
    precio: float
    allocated_fuel_eur: float
    estimated_fallback: bool
    margin_real_eur: float
    margin_estimado_legacy_eur: float
    gastos_vehiculo_ids: tuple[str, ...]


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
        KPIs financieros del mes (ingresos/gastos netos sin IVA) desde datos transaccionales
        (``facturas`` + ``gastos``), vía SQLAlchemy si hay ``DATABASE_URL``; si no, agregación en memoria.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return FinanceSummaryOut(ingresos=0.0, gastos=0.0, ebitda=0.0)
        hoy = date.today()
        period_month = self._period_month_or_current(period_month, hoy=hoy)
        factory = get_session_factory()
        if factory is not None:
            session = factory()
            try:
                ing, gas, ebitda = ftk.load_pnl_single_month(session, empresa_id=eid, period_month=period_month)
            finally:
                session.close()
            return FinanceSummaryOut(
                ingresos=float(quantize_currency(ing)),
                gastos=float(quantize_currency(gas)),
                ebitda=float(quantize_currency(ebitda)),
            )
        ing, gas, ebitda = await self._pnl_single_month_supabase(empresa_id=eid, period_month=period_month)
        return FinanceSummaryOut(
            ingresos=float(quantize_currency(ing)),
            gastos=float(quantize_currency(gas)),
            ebitda=float(quantize_currency(ebitda)),
        )

    async def financial_dashboard(
        self,
        *,
        empresa_id: str,
        hoy: date | None = None,
        period_month: str | None = None,
    ) -> FinanceDashboardOut:
        """
        Dashboard financiero desde datos transaccionales (facturas, gastos, ``bank_transactions``
        conciliadas tipo GoCardless). SQL agregado vía SQLAlchemy si hay ``DATABASE_URL``;
        si no, lecturas batch por Supabase + agregación O(n) sin N+1.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return self._finance_dashboard_empty_shell(hoy=date.today())

        if hoy is None:
            hoy = date.today()
        period_month = self._period_month_or_current(period_month, hoy=hoy)

        factory = get_session_factory()
        if factory is not None:
            session = factory()
            try:
                agg = ftk.load_transactional_dashboard(
                    session, empresa_id=eid, hoy=hoy, period_month=period_month
                )
            finally:
                session.close()
        else:
            agg = await self._transactional_dashboard_via_supabase(
                empresa_id=eid, hoy=hoy, period_month=period_month
            )

        base = self._finance_dashboard_from_agg(agg=agg, hoy=hoy, period_month=period_month)
        co2, kg_lit = await self._co2_savings_ytd_kg(empresa_id=eid, hoy=hoy)
        from app.services.bi_service import BiService

        rutas = await BiService(self._db).logisadvisor_rutas_margen_negativo(
            empresa_id=eid,
            date_from=date(hoy.year, 1, 1),
            date_to=hoy,
        )
        return base.model_copy(
            update={
                "co2_savings_ytd": co2,
                "kg_co2_por_litro_diesel_certificado": kg_lit,
                "rutas_margen_negativo_logisadvisor": rutas,
            }
        )

    async def _co2_savings_ytd_kg(self, *, empresa_id: str, hoy: date) -> tuple[float, float]:
        """
        kg CO₂ evitados YTD (año natural) priorizando `esg_co2_ahorro_vs_euro_iii_kg` en portes;
        respaldo: litros estimados desde tickets combustible × factor 2,67 kg/L × mejora de normativa.
        """
        kg_lit = float(os.getenv("ECO_KG_CO2_POR_LITRO_DIESEL") or str(KG_CO2_POR_LITRO_DIESEL))
        eid = str(empresa_id or "").strip()
        if not eid:
            return 0.0, kg_lit
        d0 = date(hoy.year, 1, 1)
        total = 0.0
        try:
            res_p: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("portes")
                    .select("esg_co2_ahorro_vs_euro_iii_kg")
                    .eq("empresa_id", eid)
                    .gte("fecha", d0.isoformat())
                    .lte("fecha", hoy.isoformat())
                )
            )
            for row in (res_p.data or []) if hasattr(res_p, "data") else []:
                v = row.get("esg_co2_ahorro_vs_euro_iii_kg")
                if v is not None:
                    total += max(0.0, float(v))
        except Exception:
            total = 0.0
        if total > 1e-9:
            return round(total, 4), kg_lit

        # Respaldo: litros desde gastos combustible YTD × factor certificado (sin desglose Euro IV/VI en fila).
        litros = 0.0
        try:
            res_gv: Any = await self._db.execute(
                filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
            )
            gas_rows: list[dict[str, Any]] = (res_gv.data or []) if hasattr(res_gv, "data") else []
        except Exception:
            gas_rows = []
        for r in gas_rows:
            fd = self._fecha_desde_campo(r.get("fecha"))
            if fd is None or fd < d0 or fd > hoy:
                continue
            if self._bucket_gasto_cinco(str(r.get("categoria") or "")) != "Combustible":
                continue
            net = self._gasto_neto_sin_iva(r)
            if net <= 0:
                continue
            litros += float(net) / max(float(EUR_POR_LITRO_DIESEL_REF), 1e-6)
        # Mejora conservadora: Euro VI vs mix anterior (≈15 % menos CO₂ por litro combustible).
        mejor_lit = 0.15
        return round(max(0.0, litros * kg_lit * mejor_lit), 4), kg_lit

    async def _pnl_single_month_supabase(self, *, empresa_id: str, period_month: str) -> tuple[Decimal, Decimal, Decimal]:
        eid = str(empresa_id or "").strip()
        y, m = int(period_month[:4]), int(period_month[5:7])
        ms = date(y, m, 1)
        if m == 12:
            me = date(y + 1, 1, 1)
        else:
            me = date(y, m + 1, 1)
        res_f: Any = await self._db.execute(
            self._db.table("facturas")
            .select("base_imponible, total_factura, cuota_iva, fecha_emision, empresa_id")
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        res_g: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_g.data or []) if hasattr(res_g, "data") else []
        ing = Decimal("0.00")
        gas = Decimal("0.00")
        for r in fact_rows:
            fd = FinanceService._fecha_desde_campo(r.get("fecha_emision"))
            if fd is None or not (ms <= fd < me):
                continue
            ing += FinanceService._ingreso_neto_sin_iva(r)
        for r in gas_rows:
            fd = FinanceService._fecha_desde_campo(r.get("fecha"))
            if fd is None or not (ms <= fd < me):
                continue
            gas += FinanceService._gasto_neto_sin_iva(r)
        return ing, gas, ing - gas

    async def _transactional_dashboard_via_supabase(
        self, *, empresa_id: str, hoy: date, period_month: str
    ) -> ftk.TransactionalDashboardAgg:
        eid = str(empresa_id or "").strip()
        res_f: Any = await self._db.execute(
            self._db.table("facturas")
            .select(
                "id, empresa_id, base_imponible, total_factura, cuota_iva, fecha_emision, "
                "estado_cobro, matched_transaction_id, pago_id, total_km_estimados_snapshot, "
                "is_finalized, hash_registro, fingerprint"
            )
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        res_g: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_g.data or []) if hasattr(res_g, "data") else []
        res_b: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("empresa_id, reconciled, amount, transaction_id, booked_date")
            .eq("empresa_id", eid)
        )
        bank_rows: list[dict[str, Any]] = (res_b.data or []) if hasattr(res_b, "data") else []
        gv_rows: list[dict[str, Any]] = []
        try:
            res_gv: Any = await self._db.execute(
                self._db.table("gastos_vehiculo").select("gasto_id").eq("empresa_id", eid).is_("deleted_at", "null")
            )
            gv_rows = (res_gv.data or []) if hasattr(res_gv, "data") else []
        except Exception:
            try:
                res_gv2: Any = await self._db.execute(
                    self._db.table("gastos_vehiculo").select("gasto_id").eq("empresa_id", eid)
                )
                gv_rows = (res_gv2.data or []) if hasattr(res_gv2, "data") else []
            except Exception:
                gv_rows = []
        fuel_ids = {str(r.get("gasto_id") or "").strip() for r in gv_rows if r.get("gasto_id")}
        return ftk.aggregate_dashboard_from_rows(
            empresa_id=eid,
            hoy=hoy,
            period_month=period_month,
            fact_rows=fact_rows,
            gasto_rows=gas_rows,
            bank_rows=bank_rows,
            fuel_gasto_ids=fuel_ids,
        )

    def _finance_dashboard_empty_shell(self, *, hoy: date) -> FinanceDashboardOut:
        bars = ftk.last_n_month_keys(hoy=hoy, n=6)
        buckets = ["Combustible", "Personal", "Mantenimiento", "Seguros", "Peajes"]
        kg_co2 = float(os.getenv("ECO_KG_CO2_POR_LITRO_DIESEL") or str(KG_CO2_POR_LITRO_DIESEL))
        return FinanceDashboardOut(
            ingresos=0.0,
            gastos=0.0,
            ebitda=0.0,
            total_km_estimados_snapshot=0.0,
            margen_km_eur=None,
            ingresos_vs_gastos_mensual=[
                FinanceMensualBarOut(periodo=p, ingresos=0.0, gastos=0.0) for p in bars
            ],
            tesoreria_mensual=[
                FinanceTesoreriaMensualOut(periodo=p, ingresos_facturados=0.0, cobros_reales=0.0)
                for p in bars
            ],
            gastos_por_bucket_cinco=[GastoBucketCincoOut(name=n, value=0.0) for n in buckets],
            gastos_bucket_mensual=[
                GastoBucketMensualOut(
                    periodo=p,
                    buckets=[GastoBucketCincoOut(name=n, value=0.0) for n in buckets],
                )
                for p in bars
            ],
            rutas_margen_negativo_logisadvisor=[],
            co2_savings_ytd=0.0,
            kg_co2_por_litro_diesel_certificado=kg_co2,
            margen_neto_km_mes_actual=None,
            margen_neto_km_mes_anterior=None,
            variacion_margen_km_pct=None,
            km_facturados_mes_actual=None,
            km_facturados_mes_anterior=None,
        )

    def _finance_dashboard_from_agg(
        self,
        *,
        agg: ftk.TransactionalDashboardAgg,
        hoy: date,
        period_month: str,
    ) -> FinanceDashboardOut:
        ing_q = quantize_currency(agg.ingresos_mes)
        gas_q = quantize_currency(agg.gastos_mes)
        ebitda_q = quantize_currency(agg.ebitda_mes)
        km_snap = quantize_currency(agg.total_km_snapshot_mes)
        margen_km: float | None = None
        if km_snap > 0:
            margen_km = float(quantize_currency(ebitda_q / km_snap))

        bars = ftk.last_n_month_keys(hoy=hoy, n=6)
        serie_bars = [
            FinanceMensualBarOut(
                periodo=p,
                ingresos=float(quantize_currency(agg.ingresos_vs_gastos_mensual.get(p, (Decimal("0.00"), Decimal("0.00")))[0])),
                gastos=float(quantize_currency(agg.ingresos_vs_gastos_mensual.get(p, (Decimal("0.00"), Decimal("0.00")))[1])),
            )
            for p in bars
        ]

        bars6 = ftk.last_n_month_keys(hoy=hoy, n=6)
        tesoreria: list[FinanceTesoreriaMensualOut] = []
        for p in bars6:
            ing_f = quantize_currency(agg.tesoreria_ing_facturado.get(p, Decimal("0.00")))
            if agg.has_bank_transactions:
                cob = quantize_currency(agg.tesoreria_cobros_reales.get(p, Decimal("0.00")))
            else:
                cob = Decimal("0.00")
            tesoreria.append(
                FinanceTesoreriaMensualOut(
                    periodo=p,
                    ingresos_facturados=float(ing_f),
                    cobros_reales=float(cob),
                )
            )

        bucket_order = ("Combustible", "Personal", "Mantenimiento", "Seguros", "Peajes")
        gastos_buckets = [
            GastoBucketCincoOut(
                name=name,
                value=float(quantize_currency(agg.gastos_bucket_ytd.get(name, Decimal("0.00")))),
            )
            for name in bucket_order
        ]
        gastos_mensual: list[GastoBucketMensualOut] = []
        for p in bars6:
            per_m = agg.gastos_bucket_por_mes.get(p, {})
            gastos_mensual.append(
                GastoBucketMensualOut(
                    periodo=p,
                    buckets=[
                        GastoBucketCincoOut(
                            name=name,
                            value=float(quantize_currency(per_m.get(name, Decimal("0.00")))),
                        )
                        for name in bucket_order
                    ],
                )
            )

        km_act = quantize_currency(agg.km_mes_actual)
        km_prev = quantize_currency(agg.km_mes_anterior)
        _, mkm_cur = self._recalculate_ebitda_and_margen_km(
            ingresos=agg.ingresos_mes, gastos=agg.gastos_mes, km_facturados=km_act
        )
        _, mkm_prev = self._recalculate_ebitda_and_margen_km(
            ingresos=agg.ingresos_prev_mes,
            gastos=agg.gastos_prev_mes,
            km_facturados=km_prev,
        )
        var_pct: float | None = None
        if mkm_cur is not None and mkm_prev is not None and mkm_prev != 0:
            var_pct = round(float((mkm_cur - mkm_prev) / mkm_prev * Decimal("100")), 4)

        kg_co2 = float(os.getenv("ECO_KG_CO2_POR_LITRO_DIESEL") or str(KG_CO2_POR_LITRO_DIESEL))
        return FinanceDashboardOut(
            ingresos=float(ing_q),
            gastos=float(gas_q),
            ebitda=float(ebitda_q),
            total_km_estimados_snapshot=float(km_snap),
            margen_km_eur=margen_km,
            ingresos_vs_gastos_mensual=serie_bars,
            tesoreria_mensual=tesoreria,
            gastos_por_bucket_cinco=gastos_buckets,
            gastos_bucket_mensual=gastos_mensual,
            rutas_margen_negativo_logisadvisor=[],
            co2_savings_ytd=0.0,
            kg_co2_por_litro_diesel_certificado=kg_co2,
            margen_neto_km_mes_actual=float(mkm_cur) if mkm_cur is not None else None,
            margen_neto_km_mes_anterior=float(mkm_prev) if mkm_prev is not None else None,
            variacion_margen_km_pct=var_pct,
            km_facturados_mes_actual=float(km_act) if km_act > 0 else None,
            km_facturados_mes_anterior=float(km_prev) if km_prev > 0 else None,
        )

    @staticmethod
    def _fecha_desde_campo(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.date()
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

    _COMPLETED_PORTE_ESTADOS = frozenset({"entregado", "facturado"})

    @classmethod
    def _porte_estado_completado(cls, raw: Any) -> bool:
        return str(raw or "").strip().lower() in cls._COMPLETED_PORTE_ESTADOS

    @staticmethod
    def _norm_matricula(val: Any) -> str:
        return "".join(c for c in str(val or "").upper() if c.isalnum())

    @staticmethod
    def _km_aplicable_porte_row(row: dict[str, Any]) -> float:
        kr = row.get("km_reales")
        if kr is not None:
            try:
                return max(0.0, float(kr))
            except (TypeError, ValueError):
                pass
        try:
            return max(0.0, float(row.get("km_estimados") or 0.0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _es_categoria_combustible_gv(cat: Any) -> bool:
        c = str(cat or "").strip().lower()
        return "combust" in c or c == "combustible"

    async def _map_vehiculos_id_to_flota_id(self, *, empresa_id: str) -> dict[str, str]:
        """
        ``gastos_vehiculo.vehiculo_id`` referencia ``vehiculos``; ``portes.vehiculo_id`` referencia ``flota``.
        Empareja por UUID común o por matrícula normalizada (misma empresa).
        """
        eid = str(empresa_id or "").strip()
        out: dict[str, str] = {}
        flota_rows: list[dict[str, Any]] = []
        try:
            res_f: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota").select("id, matricula").eq("empresa_id", eid)
                )
            )
            flota_rows = (res_f.data or []) if hasattr(res_f, "data") else []
        except Exception:
            flota_rows = []

        flota_ids = {str(r.get("id")).strip() for r in flota_rows if r.get("id") is not None}
        mat_to_flota: dict[str, str] = {}
        for r in flota_rows:
            fid = str(r.get("id") or "").strip()
            if not fid:
                continue
            mat_to_flota[FinanceService._norm_matricula(r.get("matricula"))] = fid

        veh_rows: list[dict[str, Any]] = []
        try:
            res_v: Any = await self._db.execute(
                filter_not_deleted(self._db.table("vehiculos").select("id, matricula").eq("empresa_id", eid))
            )
            veh_rows = (res_v.data or []) if hasattr(res_v, "data") else []
        except Exception:
            try:
                res_v2: Any = await self._db.execute(
                    self._db.table("vehiculos").select("id, matricula").eq("empresa_id", eid)
                )
                veh_rows = (res_v2.data or []) if hasattr(res_v2, "data") else []
            except Exception:
                veh_rows = []

        for r in veh_rows:
            vid = str(r.get("id") or "").strip()
            if not vid:
                continue
            if vid in flota_ids:
                out[vid] = vid
                continue
            nm = FinanceService._norm_matricula(r.get("matricula"))
            if nm and nm in mat_to_flota:
                out[vid] = mat_to_flota[nm]
        return out

    async def link_expenses_to_portes(
        self,
        *,
        empresa_id: str,
        start_date: date,
        end_date: date,
        audit_trail: bool = True,
    ) -> dict[str, PorteFuelAllocation]:
        """
        Imputa importes de ``gastos_vehiculo`` (categoría combustible) a portes del mismo ``empresa_id``,
        mismo día y vehículo (vía mapa vehiculos→flota). Si varios portes comparten vehículo y fecha,
        reparte el coste proporcionalmente al km.

        Sin match de combustible: ``estimated_fallback=True`` y margen = precio − km×COSTE_OPERATIVO_EUR_KM.

        Si ``audit_trail``, registra en ``auditoria`` (y best-effort ``audit_logs``) el lote.
        """
        eid = str(empresa_id or "").strip()
        if not eid or start_date > end_date:
            return {}

        gv_to_flota = await self._map_vehiculos_id_to_flota_id(empresa_id=eid)
        flota_ids_known = await self._flota_id_set(eid)

        try:
            q_gv = filter_not_deleted(
                self._db.table("gastos_vehiculo")
                .select("id, vehiculo_id, fecha, categoria, importe_total, moneda")
                .eq("empresa_id", eid)
                .gte("fecha", start_date.isoformat())
                .lte("fecha", end_date.isoformat())
            )
            res_gv: Any = await self._db.execute(q_gv)
            gv_rows: list[dict[str, Any]] = (res_gv.data or []) if hasattr(res_gv, "data") else []
        except Exception:
            gv_rows = []

        fuel_by_key: dict[tuple[date, str], float] = defaultdict(float)
        gv_ids_by_key: dict[tuple[date, str], list[str]] = defaultdict(list)
        for gv in gv_rows:
            if not FinanceService._es_categoria_combustible_gv(gv.get("categoria")):
                continue
            vid_g = str(gv.get("vehiculo_id") or "").strip()
            flota_id = gv_to_flota.get(vid_g) or (vid_g if vid_g in flota_ids_known else "")
            if not flota_id:
                continue
            fd = self._fecha_desde_campo(gv.get("fecha"))
            if fd is None:
                continue
            try:
                imp = float(gv.get("importe_total") or 0.0)
            except (TypeError, ValueError):
                imp = 0.0
            if imp <= 0:
                continue
            key = (fd, flota_id)
            fuel_by_key[key] += imp
            gid = str(gv.get("id") or "").strip()
            if gid:
                gv_ids_by_key[key].append(gid)

        try:
            q_p = filter_not_deleted(
                self._db.table("portes")
                .select(
                    "id, empresa_id, fecha, vehiculo_id, km_estimados, km_reales, precio_pactado, estado"
                )
                .eq("empresa_id", eid)
                .gte("fecha", start_date.isoformat())
                .lte("fecha", end_date.isoformat())
            )
            res_p: Any = await self._db.execute(q_p)
            porte_rows: list[dict[str, Any]] = (res_p.data or []) if hasattr(res_p, "data") else []
        except Exception:
            porte_rows = []

        by_day_veh: dict[tuple[date, str], list[dict[str, Any]]] = defaultdict(list)
        for pr in porte_rows:
            if not FinanceService._porte_estado_completado(pr.get("estado")):
                continue
            fd = self._fecha_desde_campo(pr.get("fecha"))
            vid = str(pr.get("vehiculo_id") or "").strip()
            if fd is None or not vid:
                continue
            by_day_veh[(fd, vid)].append(pr)

        allocations: dict[str, PorteFuelAllocation] = {}
        audit_payload: list[dict[str, Any]] = []

        for (fd, vid), group in by_day_veh.items():
            total_km = sum(FinanceService._km_aplicable_porte_row(x) for x in group)
            key = (fd, vid)
            total_fuel = float(fuel_by_key.get(key, 0.0))
            gids = tuple(dict.fromkeys(gv_ids_by_key.get(key, [])))

            for pr in group:
                pid = str(pr.get("id") or "").strip()
                if not pid:
                    continue
                km = FinanceService._km_aplicable_porte_row(pr)
                try:
                    precio = max(0.0, float(pr.get("precio_pactado") or 0.0))
                except (TypeError, ValueError):
                    precio = 0.0

                est_margin = round(
                    precio - km * COSTE_OPERATIVO_EUR_KM,
                    2,
                )

                if total_km > 1e-9 and total_fuel > 0:
                    share = km / total_km
                    fuel_alloc = round(total_fuel * share, 4)
                    estimated_fallback = False
                    other_opex = km * OTHER_NON_FUEL_OPEX_PER_KM
                    m_real = round(precio - fuel_alloc - other_opex, 2)
                else:
                    fuel_alloc = 0.0
                    estimated_fallback = True
                    m_real = est_margin

                allocations[pid] = PorteFuelAllocation(
                    porte_id=pid,
                    fecha=fd,
                    km=km,
                    precio=precio,
                    allocated_fuel_eur=fuel_alloc,
                    estimated_fallback=estimated_fallback,
                    margin_real_eur=m_real,
                    margin_estimado_legacy_eur=est_margin,
                    gastos_vehiculo_ids=gids,
                )
                if audit_trail and not estimated_fallback and fuel_alloc > 0:
                    audit_payload.append(
                        {
                            "porte_id": pid,
                            "fecha": fd.isoformat(),
                            "vehiculo_flota_id": vid,
                            "km": km,
                            "allocated_fuel_eur": fuel_alloc,
                            "gastos_vehiculo_ids": list(gids),
                        }
                    )

        allocated_ids = set(allocations.keys())
        for pr in porte_rows:
            if not FinanceService._porte_estado_completado(pr.get("estado")):
                continue
            pid = str(pr.get("id") or "").strip()
            if not pid or pid in allocated_ids:
                continue
            fd = self._fecha_desde_campo(pr.get("fecha"))
            if fd is None:
                continue
            km = FinanceService._km_aplicable_porte_row(pr)
            try:
                precio = max(0.0, float(pr.get("precio_pactado") or 0.0))
            except (TypeError, ValueError):
                precio = 0.0
            est_margin = round(precio - km * COSTE_OPERATIVO_EUR_KM, 2)
            allocations[pid] = PorteFuelAllocation(
                porte_id=pid,
                fecha=fd,
                km=km,
                precio=precio,
                allocated_fuel_eur=0.0,
                estimated_fallback=True,
                margin_real_eur=est_margin,
                margin_estimado_legacy_eur=est_margin,
                gastos_vehiculo_ids=(),
            )

        if audit_trail and audit_payload:
            aud = AuditoriaService(self._db)
            await aud.try_log(
                empresa_id=eid,
                accion="fuel_allocated_to_portes",
                tabla="portes",
                registro_id=f"{start_date.isoformat()}_{end_date.isoformat()}",
                cambios={
                    "n": len(audit_payload),
                    "items": audit_payload[:200],
                },
            )
            try:
                await AuditLogsService(self._db).log_sensitive_action(
                    empresa_id=eid,
                    table_name="portes",
                    record_id=f"fuel_alloc_{start_date.isoformat()}_{end_date.isoformat()}",
                    action="INSERT",
                    new_value={"kind": "fuel_allocation", "items": audit_payload[:200]},
                )
            except Exception:
                pass

        return allocations

    async def _flota_id_set(self, empresa_id: str) -> set[str]:
        try:
            res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota").select("id").eq("empresa_id", empresa_id)
                )
            )
            rows = (res.data or []) if hasattr(res, "data") else []
            return {str(r.get("id")).strip() for r in rows if r.get("id") is not None}
        except Exception:
            return set()

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

        oldest_pk = claves6[0]
        y0, m0 = int(oldest_pk[:4]), int(oldest_pk[5:7])
        range_start_pnl = date(y0, m0, 1)
        pnl_links = await self.link_expenses_to_portes(
            empresa_id=eid,
            start_date=range_start_pnl,
            end_date=hoy,
            audit_trail=False,
        )
        real_margin_index: float | None = None
        fuel_efficiency_ratio: float | None = None
        if pnl_links:
            sum_est = sum(v.margin_estimado_legacy_eur for v in pnl_links.values())
            sum_real = sum(v.margin_real_eur for v in pnl_links.values())
            sum_rev = sum(v.precio for v in pnl_links.values())
            sum_fuel = sum(v.allocated_fuel_eur for v in pnl_links.values())
            if abs(sum_est) > 1e-6:
                real_margin_index = round((sum_real - sum_est) / abs(sum_est) * 100.0, 4)
            if sum_fuel > 1e-6:
                fuel_efficiency_ratio = round(sum_rev / sum_fuel, 4)

        return AdvancedMetricsOut(
            meses=meses,
            generado_en=hoy.isoformat(),
            nota_metodologia=(
                "Ingresos y gastos sin IVA. Coste/km = (combustible + peajes + mantenimiento bucket) / km portes. "
                "CO₂ = Scope 1 combustible (tickets) + huella t·km portes. "
                "KPIs real_margin_index / fuel_efficiency_ratio: margen por porte completado con combustible "
                f"imputado desde gastos_vehiculo (mismo vehículo/día, reparto por km) + opex no combustible "
                f"({OTHER_NON_FUEL_OPEX_PER_KM} €/km); si no hay ticket, fallback km×{COSTE_OPERATIVO_EUR_KM}."
            ),
            real_margin_index=real_margin_index,
            fuel_efficiency_ratio=fuel_efficiency_ratio,
        )
