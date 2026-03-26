from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.math_engine import FinancialDomainError, round_fiat, to_decimal


def test_to_decimal_from_string_without_float_hop() -> None:
    assert to_decimal("0.1") == Decimal("0.1")
    assert to_decimal("123.4500") == Decimal("123.4500")


def test_to_decimal_from_numeric_preserves_exact_decimal_string() -> None:
    assert to_decimal(Decimal("7.125")) == Decimal("7.125")
    assert to_decimal(2) == Decimal("2")


def test_to_decimal_invalid_raises_domain_error() -> None:
    with pytest.raises(FinancialDomainError):
        to_decimal("abc-not-a-number")


def test_round_fiat_uses_half_up() -> None:
    assert round_fiat(Decimal("2.675")) == Decimal("2.68")
    assert round_fiat(Decimal("2.685")) == Decimal("2.69")
