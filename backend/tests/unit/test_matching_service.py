"""Tests del motor de emparejamiento banco ↔ facturas (sin base de datos)."""

from __future__ import annotations

import pytest

from app.services.matching_service import (
    MatchingService,
    _amount_matches_invoice,
    _date_alignment_score,
    combined_confidence_score,
)


def test_amount_matches_invoice_abs_sign() -> None:
    tx = {"amount": "-120.50"}
    inv = {"total_factura": "120.50"}
    assert _amount_matches_invoice(tx, inv) is True
    tx2 = {"amount": "120.50"}
    assert _amount_matches_invoice(tx2, inv) is True
    assert _amount_matches_invoice({"amount": "120.51"}, inv) is False
    assert _amount_matches_invoice({"amount": "0"}, inv) is False
    assert _amount_matches_invoice(tx, {"total_factura": "0"}) is False


def test_date_alignment_score_window() -> None:
    from datetime import date, timedelta

    d0 = date(2025, 1, 15)
    assert _date_alignment_score(d0, d0) == pytest.approx(1.0)
    # 29 días → 1 - 29/30 (el día 30 exacto da 0.0)
    assert _date_alignment_score(d0, d0 + timedelta(days=29)) == pytest.approx(1.0 / 30.0)
    assert _date_alignment_score(d0, d0 + timedelta(days=30)) == 0.0
    assert _date_alignment_score(None, d0) == 0.5


def test_combined_confidence_high_on_exact_ref_and_close_dates() -> None:
    tx = {
        "remittance_information": "Factura F-2024-99 ACME SL",
        "booked_date": "2025-01-10",
    }
    inv = {
        "numero_factura": "F-2024-99",
        "cliente_nombre": "ACME SL",
        "fecha_emision": "2025-01-12",
    }
    s = combined_confidence_score(transaction=tx, invoice=inv)
    assert s > 0.85


def test_find_best_candidates_one_to_one_greedy() -> None:
    svc = MatchingService.__new__(MatchingService)  # type: ignore[misc]
    txs = [
        {"transaction_id": "t1", "amount": "100.00", "booked_date": "2025-01-01", "remittance_information": "INV-A"},
        {"transaction_id": "t2", "amount": "200.00", "booked_date": "2025-01-02", "remittance_information": "INV-B"},
    ]
    invs = [
        {"id": 1, "total_factura": "100.00", "numero_factura": "INV-A", "cliente_nombre": "", "fecha_emision": "2025-01-01"},
        {"id": 2, "total_factura": "200.00", "numero_factura": "INV-B", "cliente_nombre": "", "fecha_emision": "2025-01-02"},
    ]
    matches, used_inv, used_tx = svc.find_best_candidates(transactions=txs, invoices=invs, threshold=0.5)
    assert len(matches) == 2
    assert used_inv == {1, 2}
    assert used_tx == {"t1", "t2"}
    by_tx = {m.transaction_id: m.factura_id for m in matches}
    assert by_tx["t1"] == 1
    assert by_tx["t2"] == 2


def test_find_best_candidates_picks_higher_score_same_amount() -> None:
    svc = MatchingService.__new__(MatchingService)  # type: ignore[misc]
    txs = [
        {
            "transaction_id": "tx1",
            "amount": "50.00",
            "booked_date": "2025-06-01",
            "remittance_information": "FACTURA ZZ-77 CLIENTE X",
        },
    ]
    invs = [
        {
            "id": 10,
            "total_factura": "50.00",
            "numero_factura": "OTHER",
            "cliente_nombre": "Otro",
            "fecha_emision": "2024-01-01",
        },
        {
            "id": 11,
            "total_factura": "50.00",
            "numero_factura": "ZZ-77",
            "cliente_nombre": "CLIENTE X",
            "fecha_emision": "2025-06-02",
        },
    ]
    matches, _, _ = svc.find_best_candidates(transactions=txs, invoices=invs, threshold=0.5)
    assert len(matches) == 1
    assert matches[0].factura_id == 11
    assert matches[0].score >= 0.85
