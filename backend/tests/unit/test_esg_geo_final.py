"""Pure-logic QA tests for ESG weight inference, monthly aggregation, geo cache keys, and Decimal CO2."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import MagicMock

import pytest

from app.core.esg_engine import euro_vi_factor_kg_per_km_for_weight_class, infer_weight_class_from_vehicle_label
from app.services.esg_service import EsgService
from app.services.geo_service import geocode_cache_key


class _MockExecResult:
    __slots__ = ("data",)

    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _MockSupabasePortesOnly:
    """Minimal async DB stub: only ``execute`` returning portes rows (no real PostgREST)."""

    def __init__(self, portes_rows: list[dict]) -> None:
        self._portes_rows = portes_rows
        self.table = MagicMock()

    async def execute(self, _query: object) -> _MockExecResult:  # noqa: ARG002
        return _MockExecResult(self._portes_rows)


@pytest.mark.parametrize(
    ("label", "expected_weight_class", "expected_factor"),
    [
        ("12t", "MEDIUM", 0.78),
        ("40 Toneladas", "ARTIC", 0.90),
        ("furgoneta", "UNKNOWN", 0.82),
        ("artic", "ARTIC", 0.90),
    ],
)
def test_infer_weight_class_maps_to_euro_vi_factor(
    label: str,
    expected_weight_class: str,
    expected_factor: float,
) -> None:
    wc = infer_weight_class_from_vehicle_label(label)
    assert wc == expected_weight_class
    assert euro_vi_factor_kg_per_km_for_weight_class(wc) == pytest.approx(expected_factor)


def test_get_monthly_company_report_groups_by_calendar_month_and_decimals() -> None:
    """Portes on 2026-03-31 vs 2026-04-01 must land in distinct YYYY-MM buckets."""
    portes_rows = [
        {
            "fecha": "2026-03-31",
            "real_distance_meters": 100_000.0,
            "co2_kg": "12.500000",
            "factor_emision_aplicado": "0.680000",
        },
        {
            "fecha": "2026-04-01",
            "real_distance_meters": 50_000.0,
            "co2_kg": "5.250000",
            "factor_emision_aplicado": "0.210000",
        },
    ]
    svc = EsgService(_MockSupabasePortesOnly(portes_rows), MagicMock())

    import asyncio

    report = asyncio.run(svc.get_monthly_company_report(empresa_id="empresa-test-uuid"))
    assert report.empresa_id == "empresa-test-uuid"
    assert len(report.rows) == 2
    by_m = {r.month: r for r in report.rows}
    assert "2026-03" in by_m and "2026-04" in by_m
    m03 = by_m["2026-03"]
    m04 = by_m["2026-04"]
    assert m03.total_portes == 1
    assert m04.total_portes == 1
    assert m03.total_distance_km == pytest.approx(100.0)
    assert m04.total_distance_km == pytest.approx(50.0)
    assert m03.total_co2_kg == pytest.approx(12.5)
    assert m04.total_co2_kg == pytest.approx(5.25)
    assert m03.avg_factor_emision == pytest.approx(0.68)
    assert m04.avg_factor_emision == pytest.approx(0.21)


def test_geocode_cache_key_normalizes_address_equivalence() -> None:
    a = "Calle Mayor, 1"
    b = "calle mayor 1 "
    assert geocode_cache_key(a) == geocode_cache_key(b)


def test_co2_kg_decimal_no_precision_loss_large_distance() -> None:
    """``float`` loses the +1 m before km × factor; Decimal keeps audit-grade residue in kg."""
    distance_m = Decimal("1000000000000000001")
    factor = Decimal("0.68")
    load_factor = Decimal("1.0")
    km_d = distance_m / Decimal("1000")
    co2_unrounded = km_d * factor * load_factor
    co2_kg = co2_unrounded.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    co2_if_float_km = Decimal(str((float(distance_m) / 1000.0) * float(factor) * float(load_factor)))
    assert co2_unrounded - co2_if_float_km == Decimal("0.00068")
    assert co2_kg == Decimal("680000000000000.000680")
