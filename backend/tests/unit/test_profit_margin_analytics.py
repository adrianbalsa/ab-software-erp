from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.math_engine import quantize_currency
from app.services.bi_service import expense_bucket_three, period_key_and_label


def test_expense_bucket_three() -> None:
    assert expense_bucket_three("combustible") == "combustible"
    assert expense_bucket_three("Combustible B") == "combustible"
    assert expense_bucket_three("Ticket Peajes AP-7") == "peajes"
    assert expense_bucket_three("servicios") == "otros"


def test_period_key_month_week() -> None:
    assert period_key_and_label(date(2026, 3, 10), "month") == ("2026-03", "2026-03")
    k, lab = period_key_and_label(date(2026, 1, 1), "week")
    assert k.startswith("2025-W") or k.startswith("2026-W")
    assert "sem." in lab


def test_profit_margin_totals_currency_quantization_half_up() -> None:
    """Los totales del servicio cuantizan en EUR con ROUND_HALF_UP (vía ``quantize_currency``)."""
    ing = quantize_currency(Decimal("100.005"))
    gas = quantize_currency(Decimal("40.005"))
    assert ing == Decimal("100.01")
    assert gas == Decimal("40.01")
    m = quantize_currency(ing - gas)
    assert m == Decimal("60.00")
