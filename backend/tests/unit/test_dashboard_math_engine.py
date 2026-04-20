"""Agregados dashboard operativos: Decimal + cuantía km (sin float(sum))."""

from __future__ import annotations

from decimal import Decimal

from pytest import approx

from app.core.math_engine import aggregate_portes_km_bultos, quantize_operational_km


def test_quantize_operational_km_half_even() -> None:
    assert quantize_operational_km("100.0004") == Decimal("100.000")
    assert quantize_operational_km("100.0005") == Decimal("100.000")


def test_aggregate_portes_km_bultos_sums_decimal() -> None:
    rows = [
        {"km_estimados": 100.1, "bultos": 2},
        {"km_estimados": "200.2", "bultos": 3},
        {"km_estimados": None, "bultos": None},
    ]
    km_d, bu = aggregate_portes_km_bultos(rows)
    assert bu == 5
    assert float(km_d) == approx(300.3, rel=0, abs=1e-9)


def test_aggregate_portes_ignores_invalid_bultos_skips_row_km_still_counts() -> None:
    rows = [
        {"km_estimados": 10.0, "bultos": "x"},
        {"km_estimados": 5.0, "bultos": 1},
    ]
    km_d, bu = aggregate_portes_km_bultos(rows)
    assert bu == 1
    assert float(km_d) == approx(15.0, rel=0, abs=1e-9)
