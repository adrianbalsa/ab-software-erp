"""Motor financiero: redondeo HALF_UP, división segura, dominio."""

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


def test_calculate_invoice_totals_rectificativa_negative_base_half_even() -> None:
    t = MathEngine.calculate_invoice_totals(
        [{"cantidad": 1, "precio_unitario": "-100.05", "tipo_iva_porcentaje": 21}],
        allow_negative_bases=True,
    )
    assert t.base_imponible_total == Decimal("-100.05")
    assert t.cuota_iva_total == Decimal("-21.01")
    assert t.total_factura == Decimal("-121.06")
    assert abs(t.total_factura - (t.base_imponible_total + t.cuota_iva_total)) < Decimal("0.001")


def test_net_margin_precision_with_many_decimal_expenses() -> None:
    """
    Verifica integridad decimal del beneficio neto tras múltiples gastos con decimales complejos.
    Beneficio neto = ingresos - suma(gastos) con ROUND_HALF_UP a céntimo.
    """
    ingresos = Decimal("12345.67")
    gastos = [
        Decimal("0.99"),
        Decimal("12.345"),
        Decimal("199.995"),
        Decimal("40.015"),
        Decimal("300.105"),
        Decimal("78.335"),
        Decimal("451.775"),
        Decimal("0.005"),
        Decimal("15.555"),
        Decimal("800.125"),
    ]

    total_gastos = sum(round_fiat(g) for g in gastos)
    beneficio_neto = round_fiat(ingresos - total_gastos)

    # Valor esperado calculado manualmente con HALF_UP línea a línea.
    assert total_gastos == Decimal("1899.29")
    assert beneficio_neto == Decimal("10446.38")
    # Identidad de control: ingresos = gastos + beneficio
    assert round_fiat(total_gastos + beneficio_neto) == round_fiat(ingresos)
