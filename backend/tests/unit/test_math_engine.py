"""
Suite QA: motor financiero (``math_engine``) y coherencia de totales (``totals_coherent``).

Ejecutar desde el directorio ``backend`` (``pythonpath`` en ``pytest.ini``)::

    cd backend && python -m pytest tests/unit/test_math_engine.py -v
"""

from __future__ import annotations

import sys
from decimal import ROUND_HALF_UP, Decimal, FloatOperation, getcontext
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
    calculate_invoice_totals,
    compute_f1_totals,
    decimal_to_db_numeric,
    initialize_global_decimal_context,
    quantize_currency,
    quantize_financial,
    recalculate_unsealed_invoice_operational_metrics,
    round_fiat,
    safe_divide,
    should_recalculate_unsealed_invoice,
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


@pytest.mark.parametrize(
    "base,iva,expected_cuota,expected_total",
    [
        (Decimal("10.05"), Decimal("21"), Decimal("2.11"), Decimal("12.16")),
        (Decimal("0.05"), Decimal("10"), Decimal("0.01"), Decimal("0.06")),
        (Decimal("0.005"), Decimal("21"), Decimal("0.00"), Decimal("0.01")),
    ],
)
def test_calculate_invoice_totals_aeat_rounding_vectors(
    base: Decimal,
    iva: Decimal,
    expected_cuota: Decimal,
    expected_total: Decimal,
) -> None:
    got = calculate_invoice_totals(base_imponible=base, tipo_iva=iva)
    assert got["base"] == quantize_currency(base)
    assert got["cuota"] == expected_cuota
    assert got["total"] == expected_total


def test_as_float_fiat_matches_round_fiat_semantics() -> None:
    v = as_float_fiat("10.015")
    assert v == 10.02
    assert isinstance(v, float)
    assert Decimal(str(v)) == Decimal("10.02")


def test_should_recalculate_unsealed_invoice_detects_route_or_weight_change() -> None:
    assert (
        should_recalculate_unsealed_invoice(
            invoice_is_finalized=False,
            invoice_hash_registro="",
            invoice_hash_factura="",
            previous_route_km=Decimal("100.000"),
            new_route_km=Decimal("100.001"),
            previous_weight_ton=Decimal("8.000"),
            new_weight_ton=Decimal("8.000"),
        )
        is True
    )
    assert (
        should_recalculate_unsealed_invoice(
            invoice_is_finalized=True,
            invoice_hash_registro="",
            invoice_hash_factura="",
            previous_route_km=Decimal("100"),
            new_route_km=Decimal("120"),
            previous_weight_ton=Decimal("8"),
            new_weight_ton=Decimal("9"),
        )
        is False
    )


def test_recalculate_unsealed_invoice_operational_metrics_returns_decimal_outputs() -> None:
    out = recalculate_unsealed_invoice_operational_metrics(
        invoice_is_finalized=False,
        invoice_hash_registro=None,
        invoice_hash_factura=None,
        previous_route_km=Decimal("100"),
        new_route_km=Decimal("120.5"),
        previous_weight_ton=Decimal("1.000"),
        new_weight_ton=Decimal("1.250"),
        coste_operativo_eur_km=Decimal("0.62"),
        precio_factura_base=Decimal("150.00"),
    )
    assert out["recalculated"] is True
    assert out["coste_operativo"] == Decimal("93.39")
    assert out["margen_bruto"] == Decimal("56.61")


def test_recalculate_unsealed_invoice_operational_metrics_does_not_trigger_for_sealed_invoice() -> None:
    out = recalculate_unsealed_invoice_operational_metrics(
        invoice_is_finalized=True,
        invoice_hash_registro="abc123",
        invoice_hash_factura="",
        previous_route_km=Decimal("100"),
        new_route_km=Decimal("140"),
        previous_weight_ton=Decimal("1.0"),
        new_weight_ton=Decimal("1.8"),
        coste_operativo_eur_km=Decimal("0.62"),
        precio_factura_base=Decimal("150.00"),
    )
    assert out["recalculated"] is False


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


def test_global_decimal_context_verifactu_half_up_and_float_trap() -> None:
    """Tras ``initialize_global_decimal_context`` (main/conftest): HALF_UP, prec 28, trampa FloatOperation."""
    initialize_global_decimal_context()
    ctx = getcontext()
    assert ctx.rounding == ROUND_HALF_UP
    assert ctx.prec == 28
    assert ctx.traps.get(FloatOperation) is True
    # Sin ``rounding=`` explícito: usa el contexto global (HALF_UP, no banquero HALF_EVEN).
    assert Decimal("1.005").quantize(Decimal("0.01")) == Decimal("1.01")
    assert Decimal("1.015").quantize(Decimal("0.01")) == Decimal("1.02")


def test_decimal_constructor_from_binary_float_raises_float_operation_trap() -> None:
    """Con la trampa activa: ``Decimal(1.1)`` (IEEE binario) no debe pasar inadvertido."""
    initialize_global_decimal_context()
    with pytest.raises(FloatOperation):
        Decimal(1.1)


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
