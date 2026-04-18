"""
Suite de tests unitarios — Dashboard BI financiero (Gap 6.1 / resiliencia datos).

Cubre ``FinanceService`` (rutas Supabase + shell vacío + agregación) y
``finance_transactional_kpis`` (agregación en memoria y ruta SQLAlchemy mockeada).
"""

from __future__ import annotations

import sys
import types

# Entornos con ``supabase`` antiguo (sin ``AsyncClient``) rompen el import de ``app.db.supabase``.
# Este shim solo afecta la carga del módulo de tests; no sustituye integración E2E.
def _ensure_supabase_client_shim() -> None:
    try:
        from supabase.client import AsyncClient as _AsyncClientCheck  # noqa: F401, PLC0415

        _ = _AsyncClientCheck
        return
    except ImportError:
        pass
    client_mod = types.ModuleType("supabase.client")

    class AsyncClient:  # noqa: D401
        """Stub para tipado; los tests no abren conexión Supabase."""

        pass

    async def create_async_client(*_a: object, **_k: object) -> object:  # pragma: no cover
        raise RuntimeError("create_async_client no debe invocarse en tests unitarios de finanzas")

    client_mod.AsyncClient = AsyncClient
    client_mod.create_async_client = create_async_client
    sys.modules["supabase.client"] = client_mod
    root = sys.modules.get("supabase")
    if root is None:
        root = types.ModuleType("supabase")
        sys.modules["supabase"] = root

    class ClientOptions:  # noqa: D401
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

    if not hasattr(root, "ClientOptions"):
        root.ClientOptions = ClientOptions


_ensure_supabase_client_shim()

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.schemas.finance import FinanceDashboardOut
from app.services import finance_transactional_kpis as ftk
from app.services.finance_service import FinanceService


EMPRESA_ID = str(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


def _mk_session_for_sql_dashboard() -> MagicMock:
    """Devuelve 7 resultados en el orden de ``load_transactional_dashboard``."""
    mk_iter = lambda rows: MagicMock(mappings=MagicMock(return_value=rows))
    mk_first = lambda row: MagicMock(
        mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value=row)))
    )
    mk_scalar = lambda v: MagicMock(scalar=MagicMock(return_value=v))
    return MagicMock(
        execute=MagicMock(
            side_effect=[
                mk_iter([]),
                mk_first({"ingresos": Decimal("1000"), "gastos": Decimal("400"), "km_snap": Decimal("100")}),
                mk_first({"ingresos": Decimal("800"), "gastos": Decimal("300"), "km_snap": Decimal("80")}),
                mk_iter([{"ym": "2026-01", "v": Decimal("500")}]),
                mk_iter([{"ym": "2026-02", "v": Decimal("250")}]),
                mk_scalar(4),
                mk_iter(
                    [
                        {"bucket": "Combustible", "total": Decimal("120")},
                        {"bucket": "Peajes", "total": Decimal("30")},
                    ]
                ),
            ]
        )
    )


def test_last_n_month_keys_six_months_in_order() -> None:
    hoy = date(2026, 4, 18)
    keys = ftk.last_n_month_keys(hoy=hoy, n=6)
    assert keys == ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]


def test_months_of_calendar_year_length() -> None:
    assert ftk.months_of_calendar_year(2026)[0] == "2026-01"
    assert ftk.months_of_calendar_year(2026)[-1] == "2026-12"
    assert len(ftk.months_of_calendar_year(2026)) == 12


def test_aggregate_tesoreria_single_bank_tx_two_invoices_same_match_no_double_count() -> None:
    """
    Dos facturas cobradas comparten el mismo ``matched_transaction_id``;
    un único movimiento bancario conciliado debe contar **una vez** el importe.
    """
    hoy = date(2026, 4, 15)
    period_month = "2026-04"
    fact_rows = [
        {
            "id": "1",
            "empresa_id": EMPRESA_ID,
            "base_imponible": None,
            "total_factura": 500,
            "cuota_iva": 0,
            "fecha_emision": "2026-04-10",
            "estado_cobro": "cobrada",
            "matched_transaction_id": "TX-UNICO",
            "pago_id": "TX-UNICO",
            "total_km_estimados_snapshot": 0,
        },
        {
            "id": "2",
            "empresa_id": EMPRESA_ID,
            "base_imponible": None,
            "total_factura": 500,
            "cuota_iva": 0,
            "fecha_emision": "2026-04-12",
            "estado_cobro": "cobrada",
            "matched_transaction_id": "TX-UNICO",
            "pago_id": "TX-UNICO",
            "total_km_estimados_snapshot": 0,
        },
    ]
    bank_rows = [
        {
            "empresa_id": EMPRESA_ID,
            "reconciled": True,
            "amount": 500.0,
            "transaction_id": "TX-UNICO",
            "booked_date": "2026-04-15",
        }
    ]
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=hoy,
        period_month=period_month,
        fact_rows=fact_rows,
        gasto_rows=[],
        bank_rows=bank_rows,
        fuel_gasto_ids=set(),
    )
    assert agg.tesoreria_cobros_reales["2026-04"] == Decimal("500")
    assert agg.has_bank_transactions is True


def test_aggregate_tesoreria_sums_multiple_reconciled_tx_same_month() -> None:
    hoy = date(2026, 3, 20)
    period_month = "2026-03"
    facts = [
        {
            "id": "10",
            "empresa_id": EMPRESA_ID,
            "base_imponible": 100,
            "total_factura": None,
            "cuota_iva": None,
            "fecha_emision": "2026-03-01",
            "estado_cobro": "cobrada",
            "matched_transaction_id": "A",
            "pago_id": "",
            "total_km_estimados_snapshot": 0,
        },
        {
            "id": "11",
            "empresa_id": EMPRESA_ID,
            "base_imponible": 200,
            "total_factura": None,
            "cuota_iva": None,
            "fecha_emision": "2026-03-05",
            "estado_cobro": "cobrada",
            "matched_transaction_id": "B",
            "pago_id": "",
            "total_km_estimados_snapshot": 0,
        },
    ]
    banks = [
        {
            "empresa_id": EMPRESA_ID,
            "reconciled": True,
            "amount": 100.0,
            "transaction_id": "A",
            "booked_date": "2026-03-10",
        },
        {
            "empresa_id": EMPRESA_ID,
            "reconciled": True,
            "amount": 200.0,
            "transaction_id": "B",
            "booked_date": "2026-03-12",
        },
    ]
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=hoy,
        period_month=period_month,
        fact_rows=facts,
        gasto_rows=[],
        bank_rows=banks,
        fuel_gasto_ids=set(),
    )
    assert agg.tesoreria_cobros_reales["2026-03"] == Decimal("300")


def test_aggregate_ingresos_vs_gastos_six_months_zero_fill() -> None:
    """Solo un mes con actividad; el resto de la ventana de 6 meses permanece en 0."""
    hoy = date(2026, 4, 18)
    period_month = "2026-04"
    bars = ftk.last_n_month_keys(hoy=hoy, n=6)
    fact_rows = [
        {
            "id": "1",
            "empresa_id": EMPRESA_ID,
            "base_imponible": 1000,
            "total_factura": None,
            "cuota_iva": None,
            "fecha_emision": "2026-04-05",
            "estado_cobro": "emitida",
            "matched_transaction_id": None,
            "pago_id": None,
            "total_km_estimados_snapshot": 50,
        }
    ]
    gasto_rows = [
        {
            "id": "g1",
            "empresa_id": EMPRESA_ID,
            "fecha": "2026-04-06",
            "total_eur": 200.0,
            "total_chf": None,
            "iva": None,
            "categoria": "Material",
        }
    ]
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=hoy,
        period_month=period_month,
        fact_rows=fact_rows,
        gasto_rows=gasto_rows,
        bank_rows=[],
        fuel_gasto_ids=set(),
    )
    assert set(agg.ingresos_vs_gastos_mensual.keys()) == set(bars)
    for ym, (ing, gas) in agg.ingresos_vs_gastos_mensual.items():
        if ym == "2026-04":
            assert ing == Decimal("1000")
            assert gas == Decimal("200")
        else:
            assert ing == Decimal("0")
            assert gas == Decimal("0")


def test_bucket_combustible_via_gastos_vehiculo_overrides_category() -> None:
    """Gasto categorizado como Material pero enlazado a CSV combustible → bucket Combustible."""
    row = {
        "id": "fuel-g1",
        "empresa_id": EMPRESA_ID,
        "fecha": "2026-04-01",
        "total_eur": 80.0,
        "iva": None,
        "categoria": "Material",
    }
    assert ftk.bucket_gasto_cinco_from_row(row, fuel_gasto_ids={"fuel-g1"}) == "Combustible"


def test_bucket_general_seguros_and_peajes() -> None:
    assert (
        ftk.bucket_gasto_cinco_from_row(
            {"id": "x", "categoria": "Seguro flota"}, fuel_gasto_ids=set()
        )
        == "Seguros"
    )
    assert (
        ftk.bucket_gasto_cinco_from_row({"id": "y", "categoria": "Peaje AP-7"}, fuel_gasto_ids=set())
        == "Peajes"
    )


def test_aggregate_buckets_split_fuel_vs_general_ytd() -> None:
    hoy = date(2026, 4, 10)
    period_month = "2026-04"
    gastos = [
        {
            "id": "gf",
            "empresa_id": EMPRESA_ID,
            "fecha": "2026-04-02",
            "total_eur": 100.0,
            "iva": None,
            "categoria": "Otros",
        },
        {
            "id": "gm",
            "empresa_id": EMPRESA_ID,
            "fecha": "2026-04-03",
            "total_eur": 50.0,
            "iva": None,
            "categoria": "Material",
        },
    ]
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=hoy,
        period_month=period_month,
        fact_rows=[],
        gasto_rows=gastos,
        bank_rows=[],
        fuel_gasto_ids={"gf"},
    )
    assert agg.gastos_bucket_ytd["Combustible"] == Decimal("100")
    assert agg.gastos_bucket_ytd["Mantenimiento"] == Decimal("50")


def test_finance_dashboard_empty_shell_json_contract() -> None:
    """Tenant nuevo / sin datos: estructura completa y JSON serializable (frontend)."""
    svc = FinanceService(db=MagicMock())
    hoy = date(2026, 7, 1)
    out = svc._finance_dashboard_empty_shell(hoy=hoy)
    validated = FinanceDashboardOut.model_validate(out.model_dump())
    assert len(validated.ingresos_vs_gastos_mensual) == 6
    assert len(validated.tesoreria_mensual) == 12
    assert len(validated.gastos_por_bucket_cinco) == 5
    names = [b.name for b in validated.gastos_por_bucket_cinco]
    assert names == ["Combustible", "Personal", "Mantenimiento", "Seguros", "Peajes"]
    for b in validated.gastos_por_bucket_cinco:
        assert b.value == 0.0
    for t in validated.tesoreria_mensual:
        assert t.cobros_reales == 0.0
        assert t.ingresos_facturados == 0.0
    assert validated.margen_km_eur is None
    assert validated.km_facturados_mes_actual is None


@pytest.mark.asyncio
async def test_financial_dashboard_empty_empresa_returns_shell() -> None:
    svc = FinanceService(db=MagicMock())
    dash = await svc.financial_dashboard(empresa_id="  ", hoy=date(2026, 1, 10))
    assert len(dash.tesoreria_mensual) == 12


@pytest.mark.asyncio
async def test_financial_dashboard_supabase_path_builds_series(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.finance_service.get_session_factory", lambda: None)
    hoy = date(2026, 4, 18)
    period = "2026-04"
    fact_rows = [
        {
            "id": "f1",
            "empresa_id": EMPRESA_ID,
            "base_imponible": 300,
            "total_factura": None,
            "cuota_iva": None,
            "fecha_emision": "2026-04-08",
            "estado_cobro": "cobrada",
            "matched_transaction_id": "T1",
            "pago_id": "T1",
            "total_km_estimados_snapshot": 100,
        }
    ]
    gasto_rows = [
        {
            "id": "g1",
            "empresa_id": EMPRESA_ID,
            "fecha": "2026-04-09",
            "total_eur": 100.0,
            "iva": 10.0,
            "categoria": "Combustible",
        }
    ]
    bank_rows = [
        {
            "empresa_id": EMPRESA_ID,
            "reconciled": True,
            "amount": 300.0,
            "transaction_id": "T1",
            "booked_date": "2026-04-10",
        }
    ]
    gv_rows = [{"gasto_id": "g1"}]

    n_calls: list[int] = []

    async def _exec_seq(query: Any) -> MagicMock:
        n_calls.append(1)
        n = len(n_calls)
        if n == 1:
            return MagicMock(data=fact_rows)
        if n == 2:
            return MagicMock(data=gasto_rows)
        if n == 3:
            return MagicMock(data=bank_rows)
        return MagicMock(data=gv_rows)

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_exec_seq)
    svc = FinanceService(db=db)
    dash = await svc.financial_dashboard(empresa_id=EMPRESA_ID, hoy=hoy, period_month=period)
    assert dash.ingresos == 300.0
    assert dash.gastos == 90.0
    assert dash.ebitda == 210.0
    assert len(dash.ingresos_vs_gastos_mensual) == 6
    abril_tes = next(r for r in dash.tesoreria_mensual if r.periodo == "2026-04")
    assert abril_tes.cobros_reales == 300.0
    assert abril_tes.ingresos_facturados == 300.0


@pytest.mark.asyncio
async def test_financial_summary_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.finance_service.get_session_factory", lambda: None)
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(
                data=[
                    {
                        "empresa_id": EMPRESA_ID,
                        "base_imponible": 200,
                        "total_factura": None,
                        "cuota_iva": None,
                        "fecha_emision": "2026-02-15",
                    }
                ]
            ),
            MagicMock(
                data=[
                    {
                        "empresa_id": EMPRESA_ID,
                        "fecha": "2026-02-16",
                        "total_eur": 121.0,
                        "total_chf": None,
                        "iva": 21.0,
                        "categoria": "Otros",
                    }
                ]
            ),
        ]
    )
    svc = FinanceService(db=db)
    s = await svc.financial_summary(empresa_id=EMPRESA_ID, period_month="2026-02")
    assert s.ingresos == 200.0
    assert s.gastos == 100.0
    assert s.ebitda == 100.0


def test_load_transactional_dashboard_sql_path() -> None:
    session = _mk_session_for_sql_dashboard()
    agg = ftk.load_transactional_dashboard(
        session,
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 4, 1),
        period_month="2026-04",
    )
    assert agg.ingresos_mes == Decimal("1000")
    assert agg.has_bank_transactions is True
    assert agg.gastos_bucket_ytd["Combustible"] == Decimal("120")
    session.execute.assert_called()


def test_load_pnl_single_month_sql() -> None:
    row = {"ingresos": Decimal("50"), "gastos": Decimal("20")}
    sess = MagicMock(
        execute=MagicMock(
            return_value=MagicMock(
                mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value=row)))
            )
        )
    )
    ing, gas, ebit = ftk.load_pnl_single_month(sess, empresa_id=EMPRESA_ID, period_month="2026-05")
    assert ing == Decimal("50")
    assert gas == Decimal("20")
    assert ebit == Decimal("30")


def test_dec_invalid_returns_zero() -> None:
    assert ftk._dec(object()) == Decimal("0.00")


def test_period_yyyy_mm_edge() -> None:
    assert ftk._period_yyyy_mm(None) is None
    assert ftk._period_yyyy_mm("bad") is None
    assert ftk._period_yyyy_mm("2026") is None


def test_ingreso_neto_clamps_negative_net() -> None:
    row = {"base_imponible": None, "total_factura": 10, "cuota_iva": 50}
    assert ftk._ingreso_neto_factura_row(row) == Decimal("0.00")


def test_gasto_neto_subtracts_positive_iva() -> None:
    row = {"total_eur": 121.0, "total_chf": None, "iva": 21.0}
    assert ftk._gasto_neto_row(row) == Decimal("100.00")


def test_bucket_unknown_category_defaults_mantenimiento() -> None:
    assert ftk.bucket_gasto_cinco_from_row({"id": "z", "categoria": "Gastos varios XYZ"}, fuel_gasto_ids=set()) == "Mantenimiento"


def test_aggregate_skips_gasto_without_fecha() -> None:
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 4, 1),
        period_month="2026-04",
        fact_rows=[],
        gasto_rows=[
            {
                "id": "ghost",
                "empresa_id": EMPRESA_ID,
                "fecha": None,
                "total_eur": 999.0,
                "iva": None,
                "categoria": "Combustible",
            }
        ],
        bank_rows=[],
        fuel_gasto_ids=set(),
    )
    assert agg.gastos_mes == Decimal("0")


def test_aggregate_skips_bank_rows_bad_amount_or_date() -> None:
    facts = [
        {
            "id": "1",
            "empresa_id": EMPRESA_ID,
            "base_imponible": 100,
            "fecha_emision": "2026-04-01",
            "estado_cobro": "cobrada",
            "matched_transaction_id": "T1",
            "pago_id": "T1",
            "total_km_estimados_snapshot": 0,
        }
    ]
    banks = [
        {
            "empresa_id": EMPRESA_ID,
            "reconciled": True,
            "amount": -10.0,
            "transaction_id": "T1",
            "booked_date": "2026-04-02",
        },
        {
            "empresa_id": EMPRESA_ID,
            "reconciled": True,
            "amount": 50.0,
            "transaction_id": "T1",
            "booked_date": None,
        },
    ]
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 4, 10),
        period_month="2026-04",
        fact_rows=facts,
        gasto_rows=[],
        bank_rows=banks,
        fuel_gasto_ids=set(),
    )
    assert agg.tesoreria_cobros_reales["2026-04"] == Decimal("0")


def test_load_pnl_single_month_no_row_returns_zeros() -> None:
    sess = MagicMock(
        execute=MagicMock(
            return_value=MagicMock(
                mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
            )
        )
    )
    ing, gas, ebit = ftk.load_pnl_single_month(sess, empresa_id=EMPRESA_ID, period_month="2026-07")
    assert ing == gas == ebit == Decimal("0.00")


def test_load_transactional_dashboard_pnl_cte_populates_six_month_bar() -> None:
    """Primera consulta (CTE mensual) devuelve filas mezcladas con la ventana de 6 meses."""
    mk_iter = lambda rows: MagicMock(mappings=MagicMock(return_value=rows))
    mk_first = lambda row: MagicMock(
        mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value=row)))
    )
    mk_scalar = lambda v: MagicMock(scalar=MagicMock(return_value=v))
    pnl_rows = [
        {"ym": "2026-02", "ingresos": Decimal("10"), "gastos": Decimal("4")},
        {"ym": "2026-03", "ingresos": Decimal("20"), "gastos": Decimal("8")},
    ]
    session = MagicMock(
        execute=MagicMock(
            side_effect=[
                mk_iter(pnl_rows),
                mk_first({"ingresos": Decimal("1"), "gastos": Decimal("1"), "km_snap": Decimal("2")}),
                mk_first({"ingresos": Decimal("0"), "gastos": Decimal("0"), "km_snap": Decimal("0")}),
                mk_iter([]),
                mk_iter([]),
                mk_scalar(0),
                mk_iter([]),
            ]
        )
    )
    agg = ftk.load_transactional_dashboard(
        session,
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 4, 1),
        period_month="2026-04",
    )
    assert agg.ingresos_vs_gastos_mensual["2026-03"] == (Decimal("20"), Decimal("8"))


@pytest.mark.asyncio
async def test_economic_insights_advanced_empty_db_high_branch_coverage() -> None:
    """Ejecuta la ruta principal de ``economic_insights_advanced`` con BD vacía (resiliencia)."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(data=[]))
    svc = FinanceService(db=db)
    out = await svc.economic_insights_advanced(empresa_id=EMPRESA_ID, hoy=date(2026, 6, 15))
    assert len(out.ingresos_vs_gastos_mensual) == 12
    assert out.km_operativos_ultimos_30d == 0.0
    assert out.gastos_operativos_ultimos_30d == 0.0


def test_aggregate_period_month_january_prev_year_prev_pnl() -> None:
    """Enero: ingresos del mes anterior caen en diciembre Y-1 (límites de calendario)."""
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 1, 10),
        period_month="2026-01",
        fact_rows=[
            {
                "id": "1",
                "empresa_id": EMPRESA_ID,
                "base_imponible": 50,
                "fecha_emision": "2025-12-20",
                "estado_cobro": "emitida",
                "matched_transaction_id": None,
                "pago_id": None,
                "total_km_estimados_snapshot": 10,
            }
        ],
        gasto_rows=[
            {
                "id": "g",
                "empresa_id": EMPRESA_ID,
                "fecha": "2025-12-21",
                "total_eur": 20.0,
                "iva": None,
                "categoria": "Otros",
            }
        ],
        bank_rows=[],
        fuel_gasto_ids=set(),
    )
    assert agg.ingresos_prev_mes == Decimal("50")
    assert agg.gastos_prev_mes == Decimal("20")


def test_aggregate_skips_other_empresa_rows() -> None:
    agg = ftk.aggregate_dashboard_from_rows(
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 4, 1),
        period_month="2026-04",
        fact_rows=[
            {
                "id": "x",
                "empresa_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "base_imponible": 9999,
                "fecha_emision": "2026-04-01",
                "estado_cobro": "emitida",
                "matched_transaction_id": None,
                "pago_id": None,
                "total_km_estimados_snapshot": 0,
            }
        ],
        gasto_rows=[],
        bank_rows=[],
        fuel_gasto_ids=set(),
    )
    assert agg.ingresos_mes == Decimal("0")


def test_load_transactional_dashboard_bank_scalar_raises_marks_no_bank() -> None:
    """Si el conteo de movimientos falla, ``has_bank_transactions`` debe ser False (no abortar)."""
    mk_iter = lambda rows: MagicMock(mappings=MagicMock(return_value=rows))
    mk_first = lambda row: MagicMock(
        mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value=row)))
    )

    def _exec(*_a: object, **_k: object) -> MagicMock:
        _exec.calls += 1  # type: ignore[attr-defined]
        n = _exec.calls  # type: ignore[attr-defined]
        if n == 1:
            return mk_iter([])
        if n in (2, 3):
            return mk_first({"ingresos": Decimal("0"), "gastos": Decimal("0"), "km_snap": Decimal("0")})
        if n in (4, 5):
            return mk_iter([])
        if n == 6:
            m = MagicMock()
            m.scalar.side_effect = RuntimeError("db down")
            return m
        return mk_iter([])

    _exec.calls = 0  # type: ignore[attr-defined]
    session = MagicMock(execute=MagicMock(side_effect=_exec))
    agg = ftk.load_transactional_dashboard(
        session,
        empresa_id=EMPRESA_ID,
        hoy=date(2026, 4, 1),
        period_month="2026-04",
    )
    assert agg.has_bank_transactions is False


@pytest.mark.asyncio
async def test_financial_summary_sql_session_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """``financial_summary`` con ``DATABASE_URL`` simulado (una sesión + un execute)."""
    row = {"ingresos": Decimal("123.45"), "gastos": Decimal("67.89")}
    session = MagicMock()
    session.execute = MagicMock(
        return_value=MagicMock(
            mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value=row)))
        )
    )
    session.close = MagicMock()

    def _factory() -> MagicMock:
        return session

    monkeypatch.setattr("app.services.finance_service.get_session_factory", lambda: _factory)
    svc = FinanceService(db=MagicMock())
    out = await svc.financial_summary(empresa_id=EMPRESA_ID, period_month="2026-08")
    assert out.ingresos == 123.45
    assert out.gastos == 67.89
    session.close.assert_called_once()


def test_finance_dashboard_from_agg_variacion_pct() -> None:
    svc = FinanceService(db=MagicMock())
    agg = ftk.TransactionalDashboardAgg(
        ingresos_mes=Decimal("200"),
        gastos_mes=Decimal("100"),
        ebitda_mes=Decimal("100"),
        total_km_snapshot_mes=Decimal("50"),
        km_mes_actual=Decimal("50"),
        km_mes_anterior=Decimal("40"),
        ingresos_vs_gastos_mensual={},
        tesoreria_ing_facturado={},
        tesoreria_cobros_reales={},
        gastos_bucket_ytd={k: Decimal("0") for k in ("Combustible", "Personal", "Mantenimiento", "Seguros", "Peajes")},
        has_bank_transactions=False,
        ingresos_prev_mes=Decimal("100"),
        gastos_prev_mes=Decimal("50"),
    )
    out = svc._finance_dashboard_from_agg(agg=agg, hoy=date(2026, 5, 10), period_month="2026-05")
    assert out.variacion_margen_km_pct is not None
    assert out.margen_neto_km_mes_actual is not None
