"""Motor financiero: redondeo bancario, división segura, dominio."""

from decimal import Decimal

import pytest

from app.core.math_engine import (
    FinancialDomainError,
    MathEngine,
    assert_non_negative_fiat,
    compute_f1_totals,
    decimal_to_db_numeric,
    negate_fiat_for_rectificativa,
    require_non_negative_precio_pactado,
    round_fiat,
    safe_divide,
)


def test_round_fiat_half_up() -> None:
    # Redondeo contable ROUND_HALF_UP a 2 decimales (véase math_engine.round_fiat)
    assert round_fiat("2.675") == Decimal("2.68")
    assert round_fiat(Decimal("2.685")) == Decimal("2.69")
    assert round_fiat(10.0) == Decimal("10.00")


def test_safe_divide_zero_denominator() -> None:
    assert safe_divide(100, 0) == Decimal("0.00")
    assert safe_divide(100, None) == Decimal("0.00")
    assert safe_divide(10, 2) == Decimal("5.00")


def test_compute_f1_totals() -> None:
    b, c, t = compute_f1_totals(base_imponible=Decimal("100.00"), iva_porcentaje=21.0)
    assert b == Decimal("100.00")
    assert c == Decimal("21.00")
    assert t == Decimal("121.00")


def test_negate_fiat_rectificativa() -> None:
    assert negate_fiat_for_rectificativa(100) == Decimal("-100.00")
    assert negate_fiat_for_rectificativa(0) == Decimal("0.00")


def test_require_non_negative_precio_pactado() -> None:
    require_non_negative_precio_pactado([{"precio_pactado": 10.0}])
    with pytest.raises(FinancialDomainError):
        require_non_negative_precio_pactado([{"precio_pactado": -1.0}])


def test_assert_non_negative_fiat() -> None:
    assert_non_negative_fiat("precio", 0)
    with pytest.raises(FinancialDomainError):
        assert_non_negative_fiat("precio", -0.01)


def test_math_engine_single_line_coherent_total() -> None:
    t = MathEngine.calculate_totals(
        [{"cantidad": 1, "precio_unitario": "100.00", "tipo_iva_porcentaje": 21}]
    )
    assert t.base_imponible_total == Decimal("100.00")
    assert t.cuota_iva_total == Decimal("21.00")
    assert t.cuota_recargo_equivalencia_total == Decimal("0.00")
    assert t.total_factura == Decimal("121.00")
    assert t.total_factura == decimal_to_db_numeric(
        t.base_imponible_total + t.cuota_iva_total + t.cuota_recargo_equivalencia_total
    )


def test_math_engine_importe_cero() -> None:
    t = MathEngine.calculate_totals(
        [{"cantidad": 1, "precio_unitario": 0, "tipo_iva_porcentaje": 21}]
    )
    assert t.base_imponible_total == Decimal("0.00")
    assert t.total_factura == Decimal("0.00")


def test_math_engine_dos_tipos_iva() -> None:
    t = MathEngine.calculate_totals(
        [
            {"precio_unitario": 50, "tipo_iva_porcentaje": 21},
            {"precio_unitario": 50, "tipo_iva_porcentaje": 10},
        ]
    )
    assert len(t.desglose_por_tipo) == 2
    assert t.base_imponible_total == Decimal("100.00")
    assert t.total_factura == t.base_imponible_total + t.cuota_iva_total


def test_math_engine_recargo_equivalencia_sobre_base() -> None:
    t = MathEngine.calculate_totals(
        [
            {
                "precio_unitario": 100,
                "tipo_iva_porcentaje": 21,
                "recargo_equivalencia": True,
            }
        ]
    )
    assert t.cuota_recargo_equivalencia_total == Decimal("5.20")
    assert t.total_factura == Decimal("126.20")


def test_math_engine_descuento_global() -> None:
    t = MathEngine.calculate_totals(
        [
            {"precio_unitario": 60, "tipo_iva_porcentaje": 21},
            {"precio_unitario": 40, "tipo_iva_porcentaje": 21},
        ],
        global_discount=Decimal("10.00"),
    )
    assert t.importe_descuento_global_aplicado == Decimal("10.00")
    assert t.base_imponible_total == Decimal("90.00")
    assert t.total_factura == t.base_imponible_total + t.cuota_iva_total
