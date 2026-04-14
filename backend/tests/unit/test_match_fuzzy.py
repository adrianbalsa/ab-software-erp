"""Pruebas aisladas del módulo ``match_fuzzy`` (RapidFuzz + difflib)."""

from __future__ import annotations

from app.services.match_fuzzy import fuzzy_text_score


def test_fuzzy_text_score_exact_substring_high() -> None:
    assert fuzzy_text_score("pago factura F-99 empresa sl", "F-99") >= 0.9


def test_fuzzy_empty_inputs_zero() -> None:
    assert fuzzy_text_score("", "x") == 0.0
    assert fuzzy_text_score("a", "") == 0.0
