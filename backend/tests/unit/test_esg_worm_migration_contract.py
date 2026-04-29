"""Contrato migración ESG WORM vs código (DD §2.2 evidencia sin Postgres).

Si se edita ``20260429120000_esg_period_snapshots_km_quality.sql``, revisar este test.
"""

from __future__ import annotations

from pathlib import Path


def _migration_text() -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "supabase" / "migrations" / "20260429120000_esg_period_snapshots_km_quality.sql"
    return path.read_text(encoding="utf-8")


def test_esg_period_snapshots_immutable_trigger_present() -> None:
    sql = _migration_text()
    assert "_esg_period_snapshots_immutable" in sql
    assert "UPDATE, DELETE" in sql or "UPDATE OR DELETE" in sql
    assert "esg_period_snapshots es inmutable" in sql


def test_portes_locked_columns_match_audit_expectations() -> None:
    sql = _migration_text()
    assert "_portes_block_esg_mutation_when_locked" in sql
    for col in (
        "co2_emitido",
        "co2_kg",
        "factor_emision_aplicado",
        "real_distance_meters",
        "km_estimados",
        "esg_km_source",
    ):
        assert f"NEW.{col}" in sql, f"missing lock check for {col}"
