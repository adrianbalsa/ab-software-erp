"""
KPIs financieros transaccionales (Postgres) para BI sin N+1.

Usado por ``FinanceService`` cuando existe ``DATABASE_URL`` (SQLAlchemy).
Las expresiones de ingreso/gasto neto replican la lógica de ``FinanceService`` en SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.math_engine import quantize_currency, to_decimal


def _first_day_yyyymm(ym: str) -> date:
    return date(int(ym[:4]), int(ym[5:7]), 1)


def _add_one_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)

_NET_INGRESO_FACTURA = """
CASE
  WHEN f.base_imponible IS NOT NULL THEN CAST(f.base_imponible AS NUMERIC(20, 4))
  ELSE GREATEST(
    CAST(0 AS NUMERIC(20, 4)),
    COALESCE(CAST(f.total_factura AS NUMERIC(20, 4)), CAST(0 AS NUMERIC(20, 4)))
    - COALESCE(CAST(f.cuota_iva AS NUMERIC(20, 4)), CAST(0 AS NUMERIC(20, 4)))
  )
END
"""

_NET_GASTO = """
CASE
  WHEN g.iva IS NULL THEN
    COALESCE(CAST(g.total_eur AS NUMERIC(20, 4)), CAST(g.total_chf AS NUMERIC(20, 4)), CAST(0 AS NUMERIC(20, 4)))
  WHEN COALESCE(CAST(g.iva AS NUMERIC(20, 4)), CAST(0 AS NUMERIC(20, 4))) <= CAST(0 AS NUMERIC(20, 4)) THEN
    COALESCE(CAST(g.total_eur AS NUMERIC(20, 4)), CAST(g.total_chf AS NUMERIC(20, 4)), CAST(0 AS NUMERIC(20, 4)))
  ELSE GREATEST(
    CAST(0 AS NUMERIC(20, 4)),
    COALESCE(CAST(g.total_eur AS NUMERIC(20, 4)), CAST(g.total_chf AS NUMERIC(20, 4)), CAST(0 AS NUMERIC(20, 4)))
    - CAST(g.iva AS NUMERIC(20, 4))
  )
END
"""

# Combustible CSV (``combustible_service``) persiste fila en ``gastos_vehiculo`` enlazada al ``gastos``.
# OCR (``ocr_service``) rellena ``nif_proveedor`` / importes en ``gastos``; el bucket sigue la categoría
# salvo imputación explícita a combustible por vínculo de flota.
_BUCKET_EXPR = """
CASE
  WHEN EXISTS (
    SELECT 1 FROM public.gastos_vehiculo gv
    WHERE gv.deleted_at IS NULL
      AND gv.empresa_id = g.empresa_id
      AND trim(both from gv.gasto_id) = trim(both from g.id::text)
  ) THEN 'Combustible'
  WHEN lower(coalesce(g.categoria, '')) LIKE '%combust%' THEN 'Combustible'
  WHEN lower(coalesce(g.categoria, '')) LIKE '%seguro%' THEN 'Seguros'
  WHEN lower(coalesce(g.categoria, '')) LIKE '%peaje%' THEN 'Peajes'
  WHEN lower(coalesce(g.categoria, '')) LIKE '%dieta%'
    OR lower(coalesce(g.categoria, '')) LIKE '%nómina%'
    OR lower(coalesce(g.categoria, '')) LIKE '%nomina%'
    OR lower(coalesce(g.categoria, '')) LIKE '%personal%' THEN 'Personal'
  WHEN lower(coalesce(g.categoria, '')) LIKE '%oficina%'
    OR lower(coalesce(g.categoria, '')) LIKE '%admin%' THEN 'Personal'
  WHEN lower(coalesce(g.categoria, '')) LIKE '%manten%'
    OR lower(coalesce(g.categoria, '')) LIKE '%herramient%'
    OR lower(coalesce(g.categoria, '')) LIKE '%material%'
    OR lower(coalesce(g.categoria, '')) LIKE '%vehículo%'
    OR lower(coalesce(g.categoria, '')) LIKE '%vehiculo%' THEN 'Mantenimiento'
  WHEN trim(lower(coalesce(g.categoria, ''))) IN ('', 'otros') THEN 'Mantenimiento'
  ELSE 'Mantenimiento'
END
"""


def months_of_calendar_year(year: int) -> list[str]:
    return [f"{year:04d}-{m:02d}" for m in range(1, 13)]


def last_n_month_keys(*, hoy: date, n: int) -> list[str]:
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


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _ingreso_neto_factura_row(row: dict[str, Any]) -> Decimal:
    base = row.get("base_imponible")
    if base is not None:
        return quantize_currency(to_decimal(base))
    total = to_decimal(row.get("total_factura"))
    cuota = to_decimal(row.get("cuota_iva"))
    net = total - cuota
    if net < 0:
        net = Decimal("0.00")
    return quantize_currency(net)


def _gasto_neto_row(row: dict[str, Any]) -> Decimal:
    te = row.get("total_eur")
    gross = to_decimal(te if te is not None else row.get("total_chf"))
    iva_raw = row.get("iva")
    if iva_raw is None:
        net = gross
    else:
        iva_part = to_decimal(iva_raw)
        if iva_part <= 0:
            net = gross
        else:
            net = gross - iva_part
    if net < 0:
        net = Decimal("0.00")
    return quantize_currency(net)


def _period_yyyy_mm(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return None


def factura_verifactu_sellada(row: dict[str, Any]) -> bool:
    """
    Factura con cadena VeriFactu materializada: finalizada o con huella persistida
    (``hash_registro`` / ``fingerprint``).
    """
    if row.get("is_finalized") is True:
        return True
    for key in ("hash_registro", "fingerprint"):
        raw = row.get(key)
        if raw is not None and str(raw).strip():
            return True
    return False


def bucket_gasto_cinco_from_row(
    row: dict[str, Any],
    *,
    fuel_gasto_ids: set[str],
) -> str:
    """Misma semántica que ``FinanceService._bucket_gasto_cinco`` + vínculo ``gastos_vehiculo``."""
    gid = str(row.get("id") or "").strip()
    if gid and gid in fuel_gasto_ids:
        return "Combustible"
    c = (str(row.get("categoria") or "")).strip().lower()
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


@dataclass(slots=True)
class TransactionalDashboardAgg:
    """Agregados listos para montar ``FinanceDashboardOut``."""

    ingresos_mes: Decimal
    gastos_mes: Decimal
    ebitda_mes: Decimal
    total_km_snapshot_mes: Decimal
    km_mes_actual: Decimal
    km_mes_anterior: Decimal
    ingresos_vs_gastos_mensual: dict[str, tuple[Decimal, Decimal]]
    tesoreria_ing_facturado: dict[str, Decimal]
    tesoreria_cobros_reales: dict[str, Decimal]
    gastos_bucket_ytd: dict[str, Decimal]
    gastos_bucket_por_mes: dict[str, dict[str, Decimal]]
    has_bank_transactions: bool
    ingresos_prev_mes: Decimal
    gastos_prev_mes: Decimal


def aggregate_dashboard_from_rows(
    *,
    empresa_id: str,
    hoy: date,
    period_month: str,
    fact_rows: list[dict[str, Any]],
    gasto_rows: list[dict[str, Any]],
    bank_rows: list[dict[str, Any]],
    fuel_gasto_ids: set[str],
) -> TransactionalDashboardAgg:
    """
    Agregación O(n) en memoria (una pasada por tabla) cuando no hay sesión SQLAlchemy.
    ``bank_rows``: movimientos de ``bank_transactions``; ``fuel_gasto_ids``: ids de ``gastos``
    con fila en ``gastos_vehiculo`` (importación combustible).
    """
    eid = str(empresa_id or "").strip()
    y, m = int(period_month[:4]), int(period_month[5:7])
    cur_m_start = date(y, m, 1)
    if m == 12:
        next_m = date(y + 1, 1, 1)
    else:
        next_m = date(y, m + 1, 1)
    if m == 1:
        prev_m_start = date(y - 1, 12, 1)
        prev_m_end = date(y, 1, 1)
    else:
        prev_m_start = date(y, m - 1, 1)
        prev_m_end = date(y, m, 1)

    bars = last_n_month_keys(hoy=hoy, n=6)
    ing_vs: dict[str, tuple[Decimal, Decimal]] = {k: (Decimal("0.00"), Decimal("0.00")) for k in bars}
    bar_set = set(bars)

    tes_ing: dict[str, Decimal] = {k: Decimal("0.00") for k in bars}
    tes_cob: dict[str, Decimal] = {k: Decimal("0.00") for k in bars}
    bucket_order = ("Combustible", "Personal", "Mantenimiento", "Seguros", "Peajes")
    gastos_bucket_mes: dict[str, dict[str, Decimal]] = {
        k: {b: Decimal("0.00") for b in bucket_order} for k in bars
    }
    bucket_acc: dict[str, Decimal] = {b: Decimal("0.00") for b in bucket_order}

    ing_m = Decimal("0.00")
    gas_m = Decimal("0.00")
    ing_prev_m = Decimal("0.00")
    gas_prev_m = Decimal("0.00")
    km_snap = Decimal("0.00")
    km_prev = Decimal("0.00")

    def _fd(val: Any) -> date | None:
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

    for r in fact_rows:
        if str(r.get("empresa_id") or "").strip() != eid:
            continue
        pk = _period_yyyy_mm(r.get("fecha_emision"))
        net = _ingreso_neto_factura_row(r)
        fd = _fd(r.get("fecha_emision"))
        if pk and pk in bar_set:
            a, b = ing_vs[pk]
            ing_vs[pk] = (a + net, b)
        if pk and pk in bar_set and factura_verifactu_sellada(r):
            tes_ing[pk] = tes_ing.get(pk, Decimal("0.00")) + net
        if fd and cur_m_start <= fd < next_m:
            ing_m += net
            km_snap += to_decimal(r.get("total_km_estimados_snapshot"))
        if fd and prev_m_start <= fd < prev_m_end:
            ing_prev_m += net
            km_prev += to_decimal(r.get("total_km_estimados_snapshot"))

    for r in gasto_rows:
        if str(r.get("empresa_id") or "").strip() != eid:
            continue
        fd = _fd(r.get("fecha"))
        if fd is None:
            continue
        net = _gasto_neto_row(r)
        pk = _period_yyyy_mm(r.get("fecha"))
        if pk and pk in bar_set:
            a, b = ing_vs[pk]
            ing_vs[pk] = (a, b + net)
        if pk and pk in bar_set:
            bname = bucket_gasto_cinco_from_row(r, fuel_gasto_ids=fuel_gasto_ids)
            gastos_bucket_mes[pk][bname] = gastos_bucket_mes[pk].get(bname, Decimal("0.00")) + net
            bucket_acc[bname] = bucket_acc.get(bname, Decimal("0.00")) + net
        if cur_m_start <= fd < next_m:
            gas_m += net
        if prev_m_start <= fd < prev_m_end:
            gas_prev_m += net

    has_bank = any(str(t.get("empresa_id") or "").strip() == eid for t in bank_rows)

    paid_tx_ids: set[str] = set()
    for r in fact_rows:
        if str(r.get("empresa_id") or "").strip() != eid:
            continue
        if str(r.get("estado_cobro") or "").strip().lower() != "cobrada":
            continue
        if not factura_verifactu_sellada(r):
            continue
        mt = str(r.get("matched_transaction_id") or "").strip()
        pid = str(r.get("pago_id") or "").strip()
        if mt:
            paid_tx_ids.add(mt)
        if pid:
            paid_tx_ids.add(pid)

    for t in bank_rows:
        if str(t.get("empresa_id") or "").strip() != eid:
            continue
        if not bool(t.get("reconciled")):
            continue
        tid = str(t.get("transaction_id") or "").strip()
        if not tid or tid not in paid_tx_ids:
            continue
        try:
            amt = Decimal(str(t.get("amount") or "0"))
        except Exception:
            amt = Decimal("0.00")
        if amt <= 0:
            continue
        bd = _fd(t.get("booked_date"))
        if bd is None:
            continue
        ym = f"{bd.year:04d}-{bd.month:02d}"
        if ym in tes_cob:
            tes_cob[ym] = tes_cob[ym] + amt

    for b in bucket_order:
        bucket_acc[b] = quantize_currency(bucket_acc[b])

    ebitda_m = ing_m - gas_m
    return TransactionalDashboardAgg(
        ingresos_mes=ing_m,
        gastos_mes=gas_m,
        ebitda_mes=ebitda_m,
        total_km_snapshot_mes=quantize_currency(km_snap),
        km_mes_actual=quantize_currency(km_snap),
        km_mes_anterior=quantize_currency(km_prev),
        ingresos_vs_gastos_mensual=ing_vs,
        tesoreria_ing_facturado=tes_ing,
        tesoreria_cobros_reales=tes_cob,
        gastos_bucket_ytd=bucket_acc,
        gastos_bucket_por_mes=gastos_bucket_mes,
        has_bank_transactions=has_bank,
        ingresos_prev_mes=ing_prev_m,
        gastos_prev_mes=gas_prev_m,
    )


def _pnl_month_sql() -> str:
    return f"""
    WITH ing AS (
      SELECT to_char(date_trunc('month', f.fecha_emision::date), 'YYYY-MM') AS ym,
             sum({_NET_INGRESO_FACTURA}) AS v
      FROM public.facturas f
      WHERE f.empresa_id = CAST(:eid AS uuid)
        AND f.fecha_emision IS NOT NULL
        AND f.fecha_emision::date >= CAST(:d0 AS date)
        AND f.fecha_emision::date < CAST(:d1 AS date)
      GROUP BY 1
    ),
    gas AS (
      SELECT to_char(date_trunc('month', g.fecha::date), 'YYYY-MM') AS ym,
             sum({_NET_GASTO}) AS v
      FROM public.gastos g
      WHERE g.empresa_id = CAST(:eid AS uuid)
        AND g.deleted_at IS NULL
        AND g.fecha IS NOT NULL
        AND g.fecha::date >= CAST(:d0 AS date)
        AND g.fecha::date < CAST(:d1 AS date)
      GROUP BY 1
    )
    SELECT COALESCE(i.ym, g.ym) AS ym,
           COALESCE(i.v, 0) AS ingresos,
           COALESCE(g.v, 0) AS gastos
    FROM ing i
    FULL OUTER JOIN gas g ON i.ym = g.ym
    """


def load_transactional_dashboard(
    session: Session,
    *,
    empresa_id: str,
    hoy: date,
    period_month: str,
) -> TransactionalDashboardAgg:
    """
    Lee facturas, gastos y ``bank_transactions`` conciliadas (GoCardless/Open Banking)
    con agregaciones en SQL (sin N+1).
    """
    eid = str(empresa_id or "").strip()
    y, m = int(period_month[:4]), int(period_month[5:7])
    cur_m_start = date(y, m, 1)
    if m == 12:
        next_m = date(y + 1, 1, 1)
    else:
        next_m = date(y, m + 1, 1)
    if m == 1:
        prev_m_start = date(y - 1, 12, 1)
        prev_m_end = date(y, 1, 1)
    else:
        prev_m_start = date(y, m - 1, 1)
        prev_m_end = date(y, m, 1)

    bars = last_n_month_keys(hoy=hoy, n=6)
    if bars:
        d_bar0 = _first_day_yyyymm(bars[0])
        d_bar1 = _add_one_month(_first_day_yyyymm(bars[-1]))
    else:
        d_bar0 = hoy.replace(day=1)
        d_bar1 = _add_one_month(d_bar0)

    ing_vs: dict[str, tuple[Decimal, Decimal]] = {k: (Decimal("0.00"), Decimal("0.00")) for k in bars}
    q_pnl = text(_pnl_month_sql())
    for row in session.execute(
        q_pnl,
        {
            "eid": eid,
            "d0": d_bar0.isoformat(),
            "d1": d_bar1.isoformat(),
        },
    ).mappings():
        ym = str(row["ym"])
        if ym in ing_vs:
            ing_vs[ym] = (_dec(row["ingresos"]), _dec(row["gastos"]))

    q_month_tot = text(
        f"""
        SELECT
          (SELECT COALESCE(sum({_NET_INGRESO_FACTURA}), 0)
             FROM public.facturas f
            WHERE f.empresa_id = CAST(:eid AS uuid)
              AND f.fecha_emision::date >= CAST(:ms AS date)
              AND f.fecha_emision::date < CAST(:me AS date)) AS ingresos,
          (SELECT COALESCE(sum({_NET_GASTO}), 0)
             FROM public.gastos g
            WHERE g.empresa_id = CAST(:eid AS uuid)
              AND g.deleted_at IS NULL
              AND g.fecha::date >= CAST(:ms AS date)
              AND g.fecha::date < CAST(:me AS date)) AS gastos,
          (SELECT COALESCE(sum(CAST(f.total_km_estimados_snapshot AS NUMERIC(20, 4))), 0)
             FROM public.facturas f
            WHERE f.empresa_id = CAST(:eid AS uuid)
              AND f.fecha_emision::date >= CAST(:ms AS date)
              AND f.fecha_emision::date < CAST(:me AS date)) AS km_snap
        """
    )
    row_cur = session.execute(
        q_month_tot,
        {"eid": eid, "ms": cur_m_start.isoformat(), "me": next_m.isoformat()},
    ).mappings().first()
    row_prev = session.execute(
        q_month_tot,
        {"eid": eid, "ms": prev_m_start.isoformat(), "me": prev_m_end.isoformat()},
    ).mappings().first()

    ing_m = _dec(row_cur["ingresos"]) if row_cur else Decimal("0.00")
    gas_m = _dec(row_cur["gastos"]) if row_cur else Decimal("0.00")
    ing_prev = _dec(row_prev["ingresos"]) if row_prev else Decimal("0.00")
    gas_prev = _dec(row_prev["gastos"]) if row_prev else Decimal("0.00")
    km_snap = _dec(row_cur["km_snap"]) if row_cur else Decimal("0.00")
    km_act = km_snap
    km_prev = _dec(row_prev["km_snap"]) if row_prev else Decimal("0.00")

    _VF_SELLADA = """
    (
      COALESCE(f.is_finalized, false) IS TRUE
      OR (f.hash_registro IS NOT NULL AND length(trim(f.hash_registro::text)) > 0)
      OR (f.fingerprint IS NOT NULL AND length(trim(f.fingerprint::text)) > 0)
    )
    """
    q_tes_ing = text(
        f"""
        SELECT to_char(date_trunc('month', f.fecha_emision::date), 'YYYY-MM') AS ym,
               sum({_NET_INGRESO_FACTURA}) AS v
          FROM public.facturas f
         WHERE f.empresa_id = CAST(:eid AS uuid)
           AND f.fecha_emision IS NOT NULL
           AND f.fecha_emision::date >= CAST(:y0 AS date)
           AND f.fecha_emision::date < CAST(:y1 AS date)
           AND {_VF_SELLADA}
         GROUP BY 1
        """
    )
    tes_ing: dict[str, Decimal] = {k: Decimal("0.00") for k in bars}
    for r in session.execute(
        q_tes_ing, {"eid": eid, "y0": d_bar0.isoformat(), "y1": d_bar1.isoformat()}
    ).mappings():
        ym = str(r["ym"])
        if ym in tes_ing:
            tes_ing[ym] = _dec(r["v"])

    q_tes_cob = text(
        f"""
        SELECT to_char(date_trunc('month', bt.booked_date), 'YYYY-MM') AS ym,
               sum(bt.amount) AS v
          FROM public.bank_transactions bt
         WHERE bt.empresa_id = CAST(:eid AS uuid)
           AND bt.reconciled IS TRUE
           AND bt.amount > 0
           AND bt.booked_date >= CAST(:y0 AS date)
           AND bt.booked_date < CAST(:y1 AS date)
           AND EXISTS (
                SELECT 1
                  FROM public.facturas f
                 WHERE f.empresa_id = bt.empresa_id
                   AND lower(coalesce(f.estado_cobro, '')) = 'cobrada'
                   AND (
                        f.matched_transaction_id = bt.transaction_id
                     OR f.pago_id = bt.transaction_id
                   )
                   AND {_VF_SELLADA}
           )
         GROUP BY 1
        """
    )
    tes_cob: dict[str, Decimal] = {k: Decimal("0.00") for k in bars}
    for r in session.execute(
        q_tes_cob, {"eid": eid, "y0": d_bar0.isoformat(), "y1": d_bar1.isoformat()}
    ).mappings():
        ym = str(r["ym"])
        if ym in tes_cob:
            tes_cob[ym] = _dec(r["v"])

    q_bank_any = text(
        """
        SELECT count(*)::int AS n
          FROM public.bank_transactions bt
         WHERE bt.empresa_id = CAST(:eid AS uuid)
        """
    )
    has_bank = False
    try:
        n0 = session.execute(q_bank_any, {"eid": eid}).scalar()
        has_bank = int(n0 or 0) > 0
    except Exception:
        has_bank = False

    q_gastos_mes_bucket = text(
        f"""
        SELECT to_char(date_trunc('month', s.fecha::date), 'YYYY-MM') AS ym,
               s.bkt AS bucket,
               sum(s.neto) AS total
          FROM (
            SELECT g.fecha,
                   {_BUCKET_EXPR} AS bkt,
                   {_NET_GASTO} AS neto
              FROM public.gastos g
             WHERE g.empresa_id = CAST(:eid AS uuid)
               AND g.deleted_at IS NULL
               AND g.fecha IS NOT NULL
               AND g.fecha::date >= CAST(:y0 AS date)
               AND g.fecha::date < CAST(:y1 AS date)
          ) s
         GROUP BY 1, 2
        """
    )
    bucket_order = ("Combustible", "Personal", "Mantenimiento", "Seguros", "Peajes")
    gastos_bucket_mes: dict[str, dict[str, Decimal]] = {
        k: {b: Decimal("0.00") for b in bucket_order} for k in bars
    }
    for r in session.execute(
        q_gastos_mes_bucket, {"eid": eid, "y0": d_bar0.isoformat(), "y1": d_bar1.isoformat()}
    ).mappings():
        ym = str(r["ym"])
        name = str(r["bucket"])
        if ym in gastos_bucket_mes and name in gastos_bucket_mes[ym]:
            gastos_bucket_mes[ym][name] = _dec(r["total"])

    bucket_acc: dict[str, Decimal] = {b: Decimal("0.00") for b in bucket_order}
    for pk in bars:
        for b in bucket_order:
            bucket_acc[b] = quantize_currency(bucket_acc[b] + gastos_bucket_mes[pk].get(b, Decimal("0.00")))

    ebitda_m = ing_m - gas_m
    return TransactionalDashboardAgg(
        ingresos_mes=ing_m,
        gastos_mes=gas_m,
        ebitda_mes=ebitda_m,
        total_km_snapshot_mes=km_snap,
        km_mes_actual=km_act,
        km_mes_anterior=km_prev,
        ingresos_vs_gastos_mensual=ing_vs,
        tesoreria_ing_facturado=tes_ing,
        tesoreria_cobros_reales=tes_cob,
        gastos_bucket_ytd=bucket_acc,
        gastos_bucket_por_mes=gastos_bucket_mes,
        has_bank_transactions=has_bank,
        ingresos_prev_mes=ing_prev,
        gastos_prev_mes=gas_prev,
    )


def load_pnl_single_month(session: Session, *, empresa_id: str, period_month: str) -> tuple[Decimal, Decimal, Decimal]:
    """Ingresos / gastos / EBITDA netos (sin IVA) para un único YYYY-MM."""
    y, m = int(period_month[:4]), int(period_month[5:7])
    ms = date(y, m, 1)
    if m == 12:
        me = date(y + 1, 1, 1)
    else:
        me = date(y, m + 1, 1)
    q = text(
        f"""
        SELECT
          (SELECT COALESCE(sum({_NET_INGRESO_FACTURA}), 0)
             FROM public.facturas f
            WHERE f.empresa_id = CAST(:eid AS uuid)
              AND f.fecha_emision::date >= CAST(:ms AS date)
              AND f.fecha_emision::date < CAST(:me AS date)) AS ingresos,
          (SELECT COALESCE(sum({_NET_GASTO}), 0)
             FROM public.gastos g
            WHERE g.empresa_id = CAST(:eid AS uuid)
              AND g.deleted_at IS NULL
              AND g.fecha::date >= CAST(:ms AS date)
              AND g.fecha::date < CAST(:me AS date)) AS gastos
        """
    )
    row = session.execute(q, {"eid": str(empresa_id).strip(), "ms": ms.isoformat(), "me": me.isoformat()}).mappings().first()
    if not row:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    ing = _dec(row["ingresos"])
    gas = _dec(row["gastos"])
    return ing, gas, ing - gas
