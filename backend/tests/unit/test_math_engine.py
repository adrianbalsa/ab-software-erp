from __future__ import annotations

from decimal import Decimal

from app.core.math_engine import InvoiceLineInput, MathEngine, quantize_financial, round_fiat


def test_round_half_even_ties() -> None:
    assert round_fiat(Decimal("0.005")) == Decimal("0.00")
    assert round_fiat(Decimal("0.015")) == Decimal("0.02")


def test_multi_iva_totals() -> None:
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100.00"),
            tipo_iva_porcentaje=Decimal("21.00"),
        ),
        InvoiceLineInput(
            indice=1,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("50.00"),
            tipo_iva_porcentaje=Decimal("10.00"),
        ),
        InvoiceLineInput(
            indice=2,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("25.00"),
            tipo_iva_porcentaje=Decimal("0.00"),
            motivo_exencion="E1",
        ),
    ]

    result = MathEngine.calculate_totals(items)
    assert result.base_imponible_total == Decimal("175.00")
    assert result.cuota_iva_total == Decimal("26.00")
    assert result.cuota_recargo_equivalencia_total == Decimal("0.00")
    assert result.cuota_retencion_irpf_total == Decimal("0.00")
    assert result.total_factura == Decimal("201.00")


def test_fiscal_formula() -> None:
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100.00"),
            tipo_iva_porcentaje=Decimal("21.00"),
            aplicar_recargo_equivalencia=True,
            retencion_irpf_porcentaje=Decimal("15.00"),
        )
    ]

    result = MathEngine.calculate_totals(items)
    assert result.base_imponible_total == Decimal("100.00")
    assert result.cuota_iva_total == Decimal("21.00")
    assert result.cuota_recargo_equivalencia_total == Decimal("5.20")
    assert result.cuota_retencion_irpf_total == Decimal("15.00")
    assert result.total_factura == Decimal("111.20")


def test_global_discount_drift() -> None:
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("0.33"),
            tipo_iva_porcentaje=Decimal("21.00"),
        ),
        InvoiceLineInput(
            indice=1,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("0.33"),
            tipo_iva_porcentaje=Decimal("21.00"),
        ),
        InvoiceLineInput(
            indice=2,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("0.33"),
            tipo_iva_porcentaje=Decimal("21.00"),
        ),
    ]

    result = MathEngine.calculate_totals(items, global_discount=Decimal("0.10"))
    assert result.importe_descuento_global_aplicado == Decimal("0.10")
    assert result.ajuste_centimos in {Decimal("0.00"), Decimal("0.01")}


def _assert_fiscal_identity(result) -> None:
    merged = (
        result.base_imponible_total
        + result.cuota_iva_total
        + result.cuota_recargo_equivalencia_total
        - result.cuota_retencion_irpf_total
    )
    assert result.total_factura == merged
    assert result.total_factura == quantize_financial(merged)


def test_cent_drift_nightmare_ten_lines_seven_point_five_percent_global() -> None:
    """
    10 líneas con precios que fuerzan reparto proporcional + corrección de deriva en una línea.
    Descuento global = 7,5 % del bruto total (EUR cuantificado).

    Nota: el motor absorbe el céntimo de deriva en ``base_imponible`` de línea; ``ajuste_centimos``
    sigue en 0,00 — la coherencia se valida vía sumatorio de líneas e identidad fiscal.
    """
    unit_prices = [
        Decimal("17.83"),
        Decimal("23.41"),
        Decimal("9.99"),
        Decimal("44.44"),
        Decimal("12.12"),
        Decimal("8.88"),
        Decimal("31.67"),
        Decimal("5.55"),
        Decimal("66.66"),
        Decimal("19.01"),
    ]
    items = [
        InvoiceLineInput(
            indice=i,
            cantidad=Decimal("1"),
            precio_unitario=unit_prices[i],
            tipo_iva_porcentaje=Decimal("21.00"),
        )
        for i in range(10)
    ]

    total_net = sum(
        quantize_financial(Decimal("1") * unit_prices[i]) for i in range(10)
    )
    total_net = quantize_financial(total_net)
    global_disc = quantize_financial(total_net * Decimal("7.5") / Decimal("100"))

    result = MathEngine.calculate_totals(items, global_discount=global_disc)
    assert result.importe_descuento_global_aplicado == global_disc

    sum_line_bases = sum(ln.base_imponible for ln in result.lineas)
    assert sum_line_bases == result.base_imponible_total
    assert sum_line_bases == quantize_financial(total_net - global_disc)

    sum_line_iva = sum(
        quantize_financial(ln.base_imponible * ln.tipo_iva_porcentaje / Decimal("100"))
        for ln in result.lineas
    )
    assert sum_line_iva == result.cuota_iva_total

    _assert_fiscal_identity(result)
    # Drift operativo encajado en bases de línea; campo formal aún no persiste el céntimo aparte
    assert result.ajuste_centimos == Decimal("0.00")


def test_full_spanish_stack_re_irpf_multi_bucket() -> None:
    """
    Pila fiscal mixta: RE solo donde aplica; 4 % sin RE; 0 % exportación; IRPF 15 % global (por línea).
    """
    items = [
        InvoiceLineInput(
            indice=0,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100.00"),
            tipo_iva_porcentaje=Decimal("21.00"),
            aplicar_recargo_equivalencia=True,
            retencion_irpf_porcentaje=Decimal("15.00"),
        ),
        InvoiceLineInput(
            indice=1,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("50.00"),
            tipo_iva_porcentaje=Decimal("10.00"),
            aplicar_recargo_equivalencia=True,
            retencion_irpf_porcentaje=Decimal("15.00"),
        ),
        InvoiceLineInput(
            indice=2,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("40.00"),
            tipo_iva_porcentaje=Decimal("4.00"),
            aplicar_recargo_equivalencia=False,
            retencion_irpf_porcentaje=Decimal("15.00"),
            motivo_exencion="No RE",
        ),
        InvoiceLineInput(
            indice=3,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("200.00"),
            tipo_iva_porcentaje=Decimal("0.00"),
            aplicar_recargo_equivalencia=False,
            retencion_irpf_porcentaje=Decimal("15.00"),
            tipo_no_sujecion="EXTRANJERO",
            motivo_exencion="EXPORT",
        ),
    ]

    result = MathEngine.calculate_totals(items)

    assert result.base_imponible_total == Decimal("390.00")
    assert result.cuota_iva_total == Decimal("27.60")
    assert result.cuota_recargo_equivalencia_total == Decimal("5.90")
    assert result.cuota_retencion_irpf_total == Decimal("58.50")
    assert result.total_factura == Decimal("365.00")

    _assert_fiscal_identity(result)

    sum_irpf_lines = sum(
        quantize_financial(ln.base_imponible * ln.retencion_irpf_porcentaje / Decimal("100"))
        for ln in result.lineas
    )
    assert sum_irpf_lines == result.cuota_retencion_irpf_total


def test_rounding_edge_near_half_cent_boundaries() -> None:
    """
    Valores apenas por encima / debajo de 0,005 €: deben cuantizar de forma estable a céntimo.
    """
    just_over = Decimal("0.0050000000001")
    just_under = Decimal("0.004999999999")
    assert quantize_financial(just_over) == Decimal("0.01")
    assert quantize_financial(just_under) == Decimal("0.00")
    assert round_fiat(just_over) == Decimal("0.01")
    assert round_fiat(just_under) == Decimal("0.00")
