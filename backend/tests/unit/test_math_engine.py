"""
Suite QA: motor financiero (``math_engine``) y coherencia de totales (``totals_coherent``).

Ejecutar desde el directorio ``backend`` (``pythonpath`` en ``pytest.ini``)::

    cd backend && python -m pytest tests/unit/test_math_engine.py -v
"""

from __future__ import annotations

import sys
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from pathlib import Path

import pytest

# ``parents[2]`` = directorio ``backend`` (``.../backend/tests/unit/`` → ``backend``).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.fiscal_logic import DEFAULT_TOTAL_TOLERANCE_EUR, totals_coherent
from app.core.math_engine import (
    FIAT_QUANT,
    RECARGO_EQUIVALENCIA_POR_IVA_PCT,
    FinancialDomainError,
    InvoiceLineInput,
    MathEngine,
    as_float_fiat,
    compute_f1_totals,
    decimal_to_db_numeric,
    quantize_currency,
    quantize_financial,
    round_fiat,
    safe_divide,
    sum_precios_pactados,
    to_decimal,
)


# ---------------------------------------------------------------------------
# 1. Precisión decimal y ROUND_HALF_UP en cuantías de moneda
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (Decimal("0.005"), Decimal("0.01")),
        (Decimal("0.015"), Decimal("0.02")),
        (Decimal("0.025"), Decimal("0.03")),
        (Decimal("0.035"), Decimal("0.04")),
        (Decimal("1.005"), Decimal("1.01")),
        (Decimal("1.015"), Decimal("1.02")),
        (Decimal("2.5"), Decimal("2.50")),
        (Decimal("2.225"), Decimal("2.23")),
        (Decimal("2.235"), Decimal("2.24")),
        (Decimal("-0.005"), Decimal("-0.01")),
        (Decimal("-0.015"), Decimal("-0.02")),
        (Decimal("-1.005"), Decimal("-1.01")),
    ],
)
def test_quantize_currency_half_up_rounding(raw: Decimal, expected: Decimal) -> None:
    assert quantize_currency(raw) == expected
    assert quantize_financial(raw) == expected
    assert round_fiat(raw) == expected
    assert decimal_to_db_numeric(raw) == expected


def test_round_fiat_from_string_preserves_no_float_binary() -> None:
    assert round_fiat("10.005") == Decimal("10.01")
    assert round_fiat("10.015") == Decimal("10.02")


def test_to_decimal_float_uses_str_convention() -> None:
    """Convención del proyecto: float vía ``str`` (evita sorpresas de IEEE)."""
    assert to_decimal(0.1) == Decimal("0.1")
    d = to_decimal(2.675)
    assert quantize_currency(d) == Decimal("2.68")


def test_compute_f1_totals_each_step_quantized_half_up() -> None:
    base, cuota, total = compute_f1_totals(base_imponible=Decimal("33.335"), iva_porcentaje=21)
    assert base == Decimal("33.34")
    assert cuota == Decimal("7.00")
    assert total == Decimal("40.34")
    assert total == quantize_currency(base + cuota)


def test_as_float_fiat_matches_round_fiat_semantics() -> None:
    v = as_float_fiat("10.015")
    assert v == 10.02
    assert isinstance(v, float)
    assert Decimal(str(v)) == Decimal("10.02")


# ---------------------------------------------------------------------------
# 2. Sin deriva float: identidad base + IVA + RE − IRPF en flujos complejos
# ---------------------------------------------------------------------------


def _fiscal_total_identity(
    base: Decimal,
    iva: Decimal,
    re: Decimal,
    irpf: Decimal,
) -> Decimal:
    return quantize_financial(base + iva + re - irpf)


def test_calculate_totals_identity_many_fractional_lines_no_float() -> None:
    """Muchas líneas con bases fraccionarias; todo en Decimal y cuantía 0,01."""
    items = [
        InvoiceLineInput(
            indice=i,
            cantidad=Decimal("3"),
            precio_unitario=Decimal("17.333"),
            tipo_iva_porcentaje=Decimal("21.00"),
            descuento_linea=Decimal("0.01") if i % 2 == 0 else Decimal("0.00"),
            aplicar_recargo_equivalencia=i % 3 == 0,
            retencion_irpf_porcentaje=Decimal("7.00"),
        )
        for i in range(24)
    ]
    r = MathEngine.calculate_totals(items)
    merged = _fiscal_total_identity(
        r.base_imponible_total,
        r.cuota_iva_total,
        r.cuota_recargo_equivalencia_total,
        r.cuota_retencion_irpf_total,
    )
    assert r.total_factura == merged
    assert r.total_factura == r.base_imponible_total + r.cuota_iva_total + r.cuota_recargo_equivalencia_total - r.cuota_retencion_irpf_total


def test_calculate_totals_global_discount_high_cardinality_identity() -> None:
    prices = [Decimal(f"{i}.{i % 10:02d}") for i in range(1, 31)]
    items = [
        InvoiceLineInput(
            indice=i,
            cantidad=Decimal("2"),
            precio_unitario=prices[i],
            tipo_iva_porcentaje=Decimal("10.00"),
            aplicar_recargo_equivalencia=True,
            retencion_irpf_porcentaje=Decimal("15"),
        )
        for i in range(len(prices))
    ]
    gross = quantize_financial(sum(quantize_financial(Decimal("2") * p) for p in prices))
    gdisc = quantize_financial(gross * Decimal("12.345") / Decimal("100"))
    r = MathEngine.calculate_totals(items, global_discount=gdisc)
    assert r.total_factura == _fiscal_total_identity(
        r.base_imponible_total,
        r.cuota_iva_total,
        r.cuota_recargo_equivalencia_total,
        r.cuota_retencion_irpf_total,
    )


def test_safe_divide_chain_no_residual_drift() -> None:
    n = safe_divide("100.00", "3")
    assert n == Decimal("33.33")
    acc = quantize_financial(n * Decimal("3"))
    assert acc == Decimal("99.99")


def test_sum_precios_pactados_then_round_no_float_intermediate() -> None:
    rows = [{"precio_pactado": "0.1"} for _ in range(10)]
    s = sum_precios_pactados(rows)
    assert s == Decimal("1.0")
    assert round_fiat(s) == Decimal("1.00")


# ---------------------------------------------------------------------------
# 3. Recargo equivalencia según tabla implementada (AEAT tipos generales)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "iva_key,re_pct",
    [
        ("21.00", Decimal("5.20")),
        ("10.00", Decimal("1.40")),
        ("4.00", Decimal("0.50")),
        ("0.00", Decimal("0.00")),
    ],
)
def test_recargo_equivalencia_pct_table_matches_code(iva_key: str, re_pct: Decimal) -> None:
    assert RECARGO_EQUIVALENCIA_POR_IVA_PCT[iva_key] == re_pct


@pytest.mark.parametrize(
    "iva_pct_str,base_str,expected_re",
    [
        ("21.00", "100.00", "5.20"),
        ("10.00", "100.00", "1.40"),
        ("4.00", "100.00", "0.50"),
        ("21.00", "33.33", "1.73"),
        ("10.00", "12.34", "0.17"),
        ("4.00", "99.99", "0.50"),
    ],
)
def test_recargo_cuota_matches_statutory_rate_on_base(
    iva_pct_str: str,
    base_str: str,
    expected_re: str,
) -> None:
    iva = Decimal(iva_pct_str)
    base = Decimal(base_str)
    stat = RECARGO_EQUIVALENCIA_POR_IVA_PCT[iva_pct_str]
    expected = quantize_financial(base * (stat / Decimal("100")))
    assert expected == Decimal(expected_re)


def test_recargo_applied_per_bucket_not_per_line_double_count() -> None:
    """Un bucket con varias líneas RE: una sola cuota RE sobre base agregada."""
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("50.00"),
            tipo_iva_porcentaje=Decimal("10.00"),
            aplicar_recargo_equivalencia=True,
        ),
        InvoiceLineInput(
            indice=1,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("50.00"),
            tipo_iva_porcentaje=Decimal("10.00"),
            aplicar_recargo_equivalencia=True,
        ),
    ]
    r = MathEngine.calculate_totals(items)
    assert r.base_imponible_total == Decimal("100.00")
    assert r.cuota_recargo_equivalencia_total == Decimal("1.40")


def test_unknown_iva_rate_recargo_zero() -> None:
    """Tipos IVA no tabulados: RE estadístico 0 % (clave ausente en mapa)."""
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100.00"),
            tipo_iva_porcentaje=Decimal("7.50"),
            aplicar_recargo_equivalencia=True,
        ),
    ]
    r = MathEngine.calculate_totals(items)
    assert r.cuota_recargo_equivalencia_total == Decimal("0.00")


# ---------------------------------------------------------------------------
# 4. Guardia fiscal totals_coherent (±0,01 EUR por defecto)
# ---------------------------------------------------------------------------


def test_totals_coherent_accepts_within_default_tolerance() -> None:
    assert totals_coherent(Decimal("100"), Decimal("21"), Decimal("121.00")) is True
    assert totals_coherent(Decimal("100"), Decimal("21"), Decimal("121.01")) is True
    assert totals_coherent(Decimal("100"), Decimal("21"), Decimal("120.99")) is True


def test_totals_coherent_rejects_over_one_cent_discrepancy() -> None:
    assert totals_coherent(Decimal("100"), Decimal("21"), Decimal("121.02")) is False
    assert totals_coherent(Decimal("100"), Decimal("21"), Decimal("120.98")) is False


def test_totals_coherent_default_tolerance_is_one_cent() -> None:
    assert DEFAULT_TOTAL_TOLERANCE_EUR == Decimal("0.01")


def test_totals_coherent_boundary_exactly_one_cent() -> None:
    """|expected − got| == 0,01 debe aceptarse (<= tolerancia)."""
    assert totals_coherent(Decimal("10.00"), Decimal("0.33"), Decimal("10.34")) is True


def test_totals_coherent_custom_tolerance_strict() -> None:
    """Tras cuantizar a céntimo, la diferencia debe superar la tolerancia personalizada."""
    assert totals_coherent(
        Decimal("100"),
        Decimal("21"),
        Decimal("121.02"),
        tolerance_eur=Decimal("0.001"),
    ) is False


def test_totals_coherent_invalid_inputs_false() -> None:
    assert totals_coherent("x", "1", "2") is False


# ---------------------------------------------------------------------------
# Regresión: integridad de redondeo del motor (levanta si desincroniza)
# ---------------------------------------------------------------------------


def test_calculate_totals_raises_rounding_integrity_on_pathological_mock() -> None:
    """
    El motor actual cuantiza ``merged`` de forma que la identidad se cumple.
    Este test documenta que ``RoundingIntegrityError`` existe si algún cambio
    rompe la coherencia interna (>= 0,001 €).
    """
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100.00"),
            tipo_iva_porcentaje=Decimal("21.00"),
        ),
    ]
    r = MathEngine.calculate_totals(items)
    check = abs(
        r.total_factura
        - (r.base_imponible_total + r.cuota_iva_total + r.cuota_recargo_equivalencia_total - r.cuota_retencion_irpf_total)
    )
    assert check < Decimal("0.001")


def test_default_decimal_context_rounding_is_half_even_for_reference() -> None:
    """Documentación: ``totals_coherent`` usa ``quantize`` con contexto por defecto."""
    assert getcontext().rounding == ROUND_HALF_EVEN


def test_fiat_quant_is_one_cent() -> None:
    assert FIAT_QUANT == Decimal("0.01")


def test_normalize_items_rejects_iva_zero_without_motivo() -> None:
    with pytest.raises(FinancialDomainError):
        MathEngine.normalize_items(
            [
                {
                    "cantidad": 1,
                    "precio_unitario": "10",
                    "tipo_iva_porcentaje": "0",
                }
            ]
        )


def test_negative_net_line_raises() -> None:
    with pytest.raises(FinancialDomainError):
        MathEngine.calculate_totals(
            [
                InvoiceLineInput(
                    indice=0,
                    cantidad=Decimal("1"),
                    precio_unitario=Decimal("5.00"),
                    tipo_iva_porcentaje=Decimal("21.00"),
                    descuento_linea=Decimal("10.00"),
                )
            ]
        )
