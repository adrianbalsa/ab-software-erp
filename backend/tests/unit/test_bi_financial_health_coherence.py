"""Coherencia KPI financial-health vs agregación de series (DD §2.3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.bi_financial_health_contract import (
    assert_financial_health_coherent,
    financial_health_coherence_issues,
)
from app.core.math_engine import FinancialAggregator, quantize_currency


def test_coherent_payload_passes() -> None:
    series = [
        {"name": "2026-01", "ingresos": 1000.0, "gastos": 400.0, "co2_cost": 25.0},
        {"name": "2026-02", "ingresos": 500.0, "gastos": 300.0, "co2_cost": 10.0},
    ]
    tot_ing = Decimal("1500")
    tot_gas = Decimal("700")
    ebitda = FinancialAggregator.calculate_ebitda_bruto(
        ingresos_operativos=tot_ing,
        costes_operativos=tot_gas,
    )
    margin = FinancialAggregator.calculate_margen_operativo(ebitda_bruto=ebitda, ventas=tot_ing)
    saldo = Decimal("1200")
    cf = FinancialAggregator.calculate_cash_flow_estimado(
        saldo_facturas_emitidas=saldo,
        gastos_registrados=tot_gas,
    )
    co2_total = sum(Decimal(str(p["co2_cost"])) for p in series)
    payload = {
        "summary": {
            "ebitda": float(ebitda),
            "operating_margin_pct": float(margin),
            "cash_flow": float(cf),
        },
        "series": series,
        "meta": {
            "ingresos_operativos": float(quantize_currency(tot_ing)),
            "costes_operativos": float(quantize_currency(tot_gas)),
            "costo_carbono_total": float(quantize_currency(co2_total)),
            "saldo_facturas_emitidas_eur": float(quantize_currency(saldo)),
        },
    }
    assert_financial_health_coherent(payload)


def test_mismatch_surfaces_issues() -> None:
    payload = {
        "summary": {"ebitda": 0.0, "operating_margin_pct": 0.0, "cash_flow": 0.0},
        "series": [{"name": "a", "ingresos": 100.0, "gastos": 10.0, "co2_cost": 1.0}],
        "meta": {
            "ingresos_operativos": 999.0,
            "costes_operativos": 10.0,
            "costo_carbono_total": 1.0,
            "saldo_facturas_emitidas_eur": 0.0,
        },
    }
    issues = financial_health_coherence_issues(
        summary=dict(payload["summary"]),
        series=list(payload["series"]),
        meta=dict(payload["meta"]),
    )
    assert any("ingresos" in m for m in issues)


def test_assert_raises_on_bad_ebitda() -> None:
    payload = {
        "summary": {"ebitda": 1.0, "operating_margin_pct": 10.0, "cash_flow": 0.0},
        "series": [{"name": "a", "ingresos": 100.0, "gastos": 40.0, "co2_cost": 5.0}],
        "meta": {
            "ingresos_operativos": 100.0,
            "costes_operativos": 40.0,
            "costo_carbono_total": 5.0,
            "saldo_facturas_emitidas_eur": 0.0,
        },
    }
    with pytest.raises(AssertionError):
        assert_financial_health_coherent(payload)
