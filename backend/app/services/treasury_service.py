from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.core.math_engine import as_float_fiat, round_fiat
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.treasury import (
    CashFlowOut,
    TreasuryArBucketOut,
    TreasuryProjectionOut,
    WaterfallMesOut,
)

_DEFAULT_DIAS_VENCIMIENTO = 30


def _parse_row_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _factura_due(row: dict[str, Any]) -> date | None:
    fv = _parse_row_date(row.get("fecha_vencimiento"))
    if fv is not None:
        return fv
    fe = _parse_row_date(row.get("fecha_emision"))
    if fe is None:
        return None
    return fe + timedelta(days=_DEFAULT_DIAS_VENCIMIENTO)


def _gasto_due(row: dict[str, Any]) -> date | None:
    fv = _parse_row_date(row.get("fecha_vencimiento"))
    if fv is not None:
        return fv
    fd = _parse_row_date(row.get("fecha"))
    if fd is None:
        return None
    return fd + timedelta(days=_DEFAULT_DIAS_VENCIMIENTO)


def _is_cobrada(row: dict[str, Any]) -> bool:
    return str(row.get("estado_cobro") or "").strip().lower() == "cobrada"


def _fecha_estimada_cobro_row(row: dict[str, Any]) -> date | None:
    fe = _parse_row_date(row.get("fecha_estimada_cobro"))
    if fe is not None:
        return fe
    return _factura_due(row)


def _mean_days(xs: list[float]) -> float | None:
    if not xs:
        return None
    return float(sum(xs) / len(xs))


def _monto_gasto_eur(row: dict[str, Any]) -> Decimal:
    te = row.get("total_eur")
    if te is not None:
        return round_fiat(te)
    return round_fiat(row.get("total_chf"))


class TreasuryService:
    """Agregados de tesorería con precisión fiat (Decimal + round_fiat)."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def cash_flow_snapshot(self, *, empresa_id: str, today: date | None = None) -> CashFlowOut:
        eid = str(empresa_id or "").strip()
        if not eid:
            raise ValueError("empresa_id requerido")
        if today is None:
            today = date.today()

        horizon = today + timedelta(days=30)

        # —— Movimientos conciliados (saldo y cascada mes) ——
        res_mov: Any = await self._db.execute(
            self._db.table("movimientos_bancarios")
            .select("importe, fecha, estado")
            .eq("empresa_id", eid)
            .eq("estado", "Conciliado")
        )
        mov_rows: list[dict[str, Any]] = (res_mov.data or []) if hasattr(res_mov, "data") else []

        saldo_actual = Decimal("0.00")
        for r in mov_rows:
            saldo_actual += round_fiat(r.get("importe"))
        saldo_actual = round_fiat(saldo_actual)

        month_start = today.replace(day=1)
        last_d = calendar.monthrange(today.year, today.month)[1]
        month_end = date(today.year, today.month, last_d)

        saldo_ini = Decimal("0.00")
        entradas = Decimal("0.00")
        salidas = Decimal("0.00")
        saldo_fin = Decimal("0.00")
        for r in mov_rows:
            imp = round_fiat(r.get("importe"))
            fd = _parse_row_date(r.get("fecha"))
            if fd is None:
                continue
            if fd < month_start:
                saldo_ini += imp
            if month_start <= fd <= month_end:
                if imp > 0:
                    entradas += imp
                elif imp < 0:
                    salidas += round_fiat(-imp)
            if fd <= month_end:
                saldo_fin += imp

        saldo_ini = round_fiat(saldo_ini)
        entradas = round_fiat(entradas)
        salidas = round_fiat(salidas)
        saldo_fin = round_fiat(saldo_fin)

        wf = WaterfallMesOut(
            saldo_inicial=as_float_fiat(saldo_ini),
            entradas_cobros=as_float_fiat(entradas),
            salidas_pagos=as_float_fiat(salidas),
            saldo_final=as_float_fiat(saldo_fin),
            mes_label=f"{today.year:04d}-{today.month:02d}",
        )

        # —— Facturas (AR) ——
        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select("total_factura, estado_cobro, fecha_emision, fecha_vencimiento")
            .eq("empresa_id", eid)
        )
        fac_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []

        ar_total = Decimal("0.00")
        ar_30 = Decimal("0.00")
        for r in fac_rows:
            if _is_cobrada(r):
                continue
            amt = round_fiat(r.get("total_factura"))
            ar_total += amt
            due = _factura_due(r)
            if due is not None and due <= horizon:
                ar_30 += amt
        ar_total = round_fiat(ar_total)
        ar_30 = round_fiat(ar_30)

        # —— Gastos (AP) ——
        q_gas = filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        res_gas: Any = await self._db.execute(q_gas)
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []

        ap_total = Decimal("0.00")
        ap_30 = Decimal("0.00")
        for r in gas_rows:
            st = str(r.get("estado_pago") or "pendiente").strip().lower()
            if st == "pagado":
                continue
            amt = _monto_gasto_eur(r)
            ap_total += amt
            due = _gasto_due(r)
            if due is not None and due <= horizon:
                ap_30 += amt
        ap_total = round_fiat(ap_total)
        ap_30 = round_fiat(ap_30)

        proyeccion = round_fiat(saldo_actual + ar_30 - ap_30)

        return CashFlowOut(
            saldo_actual_estimado=as_float_fiat(saldo_actual),
            cuentas_por_cobrar=as_float_fiat(ar_total),
            cuentas_por_pagar=as_float_fiat(ap_total),
            ar_vencimiento_30d=as_float_fiat(ar_30),
            ap_vencimiento_30d=as_float_fiat(ap_30),
            proyeccion_30_dias=as_float_fiat(proyeccion),
            waterfall_mes=wf,
        )

    async def treasury_projection(self, *, empresa_id: str, today: date | None = None) -> TreasuryProjectionOut:
        """
        AR pendiente por cubos (fecha estimada de cobro) y PMC real sobre facturas cobradas.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            raise ValueError("empresa_id requerido")
        if today is None:
            today = date.today()

        res_mov: Any = await self._db.execute(
            self._db.table("movimientos_bancarios")
            .select("importe, fecha, estado")
            .eq("empresa_id", eid)
            .eq("estado", "Conciliado")
        )
        mov_rows: list[dict[str, Any]] = (res_mov.data or []) if hasattr(res_mov, "data") else []
        saldo_actual = Decimal("0.00")
        for r in mov_rows:
            saldo_actual += round_fiat(r.get("importe"))
        saldo_actual = round_fiat(saldo_actual)

        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select(
                "total_factura, estado_cobro, fecha_emision, fecha_cobro_real, "
                "fecha_estimada_cobro, fecha_vencimiento"
            )
            .eq("empresa_id", eid)
        )
        fac_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []

        vencido = Decimal("0.00")
        prox_7 = Decimal("0.00")
        d8_15 = Decimal("0.00")
        mas_15 = Decimal("0.00")
        total_pend = Decimal("0.00")

        pmc_todos: list[float] = []
        pmc_rec: list[float] = []
        pmc_prev: list[float] = []
        win_end = today
        win_rec_start = today - timedelta(days=90)
        win_prev_end = today - timedelta(days=90)
        win_prev_start = today - timedelta(days=180)

        for r in fac_rows:
            if _is_cobrada(r):
                fe = _parse_row_date(r.get("fecha_emision"))
                fc = _parse_row_date(r.get("fecha_cobro_real"))
                if fe is not None and fc is not None:
                    dias = float((fc - fe).days)
                    if dias >= 0:
                        pmc_todos.append(dias)
                    if win_rec_start <= fc <= win_end:
                        if dias >= 0:
                            pmc_rec.append(dias)
                    if win_prev_start <= fc < win_prev_end:
                        if dias >= 0:
                            pmc_prev.append(dias)
                continue

            amt = round_fiat(r.get("total_factura"))
            total_pend += amt
            f_est = _fecha_estimada_cobro_row(r)
            if f_est is None:
                mas_15 += amt
                continue
            if f_est < today:
                vencido += amt
            elif today <= f_est <= today + timedelta(days=7):
                prox_7 += amt
            elif today + timedelta(days=8) <= f_est <= today + timedelta(days=15):
                d8_15 += amt
            else:
                mas_15 += amt

        vencido = round_fiat(vencido)
        prox_7 = round_fiat(prox_7)
        d8_15 = round_fiat(d8_15)
        mas_15 = round_fiat(mas_15)
        total_pend = round_fiat(total_pend)

        m_global = _mean_days(pmc_todos)
        m_rec = _mean_days(pmc_rec)
        m_prev = _mean_days(pmc_prev)

        tendencia: Literal["mejorando", "empeorando", "estable"] = "estable"
        if (
            m_rec is not None
            and m_prev is not None
            and len(pmc_rec) >= 3
            and len(pmc_prev) >= 3
        ):
            if m_rec < m_prev * 0.98:
                tendencia = "mejorando"
            elif m_rec > m_prev * 1.02:
                tendencia = "empeorando"
            else:
                tendencia = "estable"

        buckets = [
            TreasuryArBucketOut(
                clave="vencido",
                etiqueta="Vencido",
                importe=as_float_fiat(vencido),
            ),
            TreasuryArBucketOut(
                clave="proximos_7",
                etiqueta="Próximos 7 días",
                importe=as_float_fiat(prox_7),
            ),
            TreasuryArBucketOut(
                clave="dias_8_15",
                etiqueta="8–15 días",
                importe=as_float_fiat(d8_15),
            ),
            TreasuryArBucketOut(
                clave="mas_15",
                etiqueta="Más de 15 días",
                importe=as_float_fiat(mas_15),
            ),
        ]

        return TreasuryProjectionOut(
            fecha_referencia=today,
            saldo_en_caja=as_float_fiat(saldo_actual),
            total_pendiente_cobro=as_float_fiat(total_pend),
            buckets=buckets,
            pmc_dias=m_global,
            pmc_muestras=len(pmc_todos),
            pmc_periodo_reciente_dias=m_rec,
            pmc_periodo_anterior_dias=m_prev,
            pmc_tendencia=tendencia,
        )
