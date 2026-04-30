"""Cobertura de km ESG y resolución única de distancia para certificados GLEC."""

from __future__ import annotations

import pytest

from app.core.esg_km_quality import (
    ESG_KM_SOURCE_REGISTRY,
    build_esg_quality_report,
    esg_snapshot_content_sha256,
    explicit_estimated_overrides_distance_signals,
    infer_esg_km_source,
    km_coverage_breakdown,
    operational_km_for_row,
    resolve_total_km_for_glec_certificate,
)


def test_infer_prefers_explicit_source() -> None:
    row = {"esg_km_source": "estimated", "real_distance_meters": 100_000.0}
    assert infer_esg_km_source(row) == "estimated"


def test_infer_route_api_meters() -> None:
    row = {"real_distance_meters": 50_000.0, "km_estimados": 10.0}
    assert infer_esg_km_source(row) == "route_api_meters"


def test_infer_recorded_road_km() -> None:
    row = {"km_reales": 120.0, "km_estimados": 100.0}
    assert infer_esg_km_source(row) == "recorded_road_km"


def test_operational_km_prefers_km_reales_over_meters() -> None:
    row = {"km_reales": 99.0, "real_distance_meters": 100_000.0, "km_estimados": 80.0}
    assert operational_km_for_row(row) == 99.0


def test_resolve_glec_certificate_km_prefers_meters_over_km_reales() -> None:
    row = {"km_reales": 99.0, "real_distance_meters": 100_000.0, "km_estimados": 80.0}
    assert resolve_total_km_for_glec_certificate(row) == 100.0


def test_km_coverage_breakdown_splits_sources() -> None:
    rows = [
        {"km_estimados": 100.0, "km_reales": None, "real_distance_meters": None},
        {"km_estimados": 50.0, "km_reales": 50.0, "real_distance_meters": None},
        {"km_estimados": 10.0, "km_reales": None, "real_distance_meters": 10_000.0},
    ]
    cov = km_coverage_breakdown(rows)
    assert cov["total_km_activity"] == 100.0 + 50.0 + 10.0
    assert cov["pct_km_estimated"] > 0
    assert cov["pct_km_recorded_road_km"] > 0
    assert cov["pct_km_route_api_meters"] > 0


def test_registry_covers_all_valid_sources() -> None:
    assert set(ESG_KM_SOURCE_REGISTRY.keys()) == {
        "route_api_meters",
        "recorded_road_km",
        "telemetry",
        "estimated",
    }


def test_infer_telemetry_from_column() -> None:
    row = {"telemetry_distance_km": 88.0, "km_estimados": 100.0}
    assert infer_esg_km_source(row) == "telemetry"


def test_infer_invalid_explicit_source_falls_back() -> None:
    row = {"esg_km_source": "not_a_real_source", "km_reales": 10.0}
    assert infer_esg_km_source(row) == "recorded_road_km"


def test_km_coverage_zero_activity() -> None:
    cov = km_coverage_breakdown([{"km_estimados": 0.0}])
    assert cov["total_km_activity"] == 0.0
    assert cov["pct_km_estimated"] == 0.0


def test_explicit_estimated_override_detected() -> None:
    row = {"esg_km_source": "estimated", "real_distance_meters": 5000.0}
    assert explicit_estimated_overrides_distance_signals(row) is True


def test_build_quality_report_measured_vs_estimated() -> None:
    rows = [
        {"km_estimados": 100.0, "km_reales": None, "real_distance_meters": None},
        {"km_estimados": 0.0, "km_reales": 100.0, "real_distance_meters": None},
    ]
    rep = build_esg_quality_report(rows)
    assert rep["pct_measured_km_activity"] + rep["pct_estimated_km_activity"] == pytest.approx(100.0)
    assert rep["portes_by_source"]["recorded_road_km"] == 1
    assert rep["portes_by_source"]["estimated"] == 1


def test_build_quality_report_high_estimated_gap() -> None:
    rows = [{"km_estimados": 100.0, "km_reales": None, "real_distance_meters": None} for _ in range(10)]
    rep = build_esg_quality_report(rows)
    kinds = {g["kind"] for g in rep["gaps"]}
    assert "high_estimated_km_share" in kinds


def test_esg_snapshot_sha256_golden() -> None:
    payload = {
        "schema": "esg_period_snapshot_v1",
        "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "km_coverage": {
            "pct_km_estimated": 0.0,
            "pct_km_recorded_road_km": 0.0,
            "pct_km_route_api_meters": 0.0,
            "pct_km_telemetry": 0.0,
            "total_km_activity": 0.0,
        },
        "num_portes_facturados": 0,
        "period_month": 4,
        "period_year": 2026,
        "total_co2_kg": 0.0,
    }
    assert esg_snapshot_content_sha256(payload) == (
        "202bd3cb70ffbe0256d2bf4fe6b192c572379fc508f9ff32e5731efc86aaa8a5"
    )
