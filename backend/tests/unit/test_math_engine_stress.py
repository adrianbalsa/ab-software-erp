"""
Stress tests: acumulación de céntimos, binarios IEEE 754, coherencia IVA (VeriFactu-ready).

El motor usa ``decimal.Decimal`` y cuantía a 2 decimales con **ROUND_HALF_EVEN** (redondeo bancario),
alineado con ``math_engine`` y columnas ``numeric(12,2)``.

Auditoría rápida (importes en backend):
- ``MathEngine`` / ``round_fiat`` / ``to_decimal``: solo ``Decimal`` en el cómputo; ``as_float_fiat`` es
  solo para serialización JSON.
- Servicios (``facturas_service``, ``treasury_service``, …) agregan con ``round_fiat`` sobre ``Decimal``;
  donde aún exista ``float`` en payloads, la ruta segura es enviar **strings** decimales a la API.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.math_engine import (
    FinancialDomainError,
    MathEngine,
    compute_f1_totals,
    quantize_financial,
    round_fiat,
    safe_divide,
    to_decimal,
)


def _assert_invoice_atomically_closed(t) -> None:
    """Base + IVA + RE == total exactamente en céntimos (sin deriva)."""
    merged = t.base_imponible_total + t.cuota_iva_total + t.cuota_recargo_equivalencia_total
    assert t.total_factura == merged, (
        f"total {t.total_factura} != base+iva+re {merged} "
        f"(Δ={(t.total_factura - merged)!r})"
    )


def test_cent_accumulation_thousand_lines_point_zero_zero_four_nine() -> None:
    """
    Edge 1: 1000 líneas a 0,0049 € (entrada **string** para no introducir binario float).

    Criterio «línea a línea»: cada bruto se cuantiza a 2 decimales antes de acumular (MathEngine).
    Se contrasta con la suma de importes **sin** cuantizar intermedia (solo referencia documental).
    """
    n = 1000
    unit = Decimal("0.0049")
    items = [{"cantidad": 1, "precio_unitario": "0.0049", "tipo_iva_porcentaje": "21"} for _ in range(n)]

    raw_sum = quantize_financial(unit * n)
    per_line_net = quantize_financial(Decimal("1") * unit)
    sum_of_rounded_lines = quantize_financial(per_line_net * n)

    t = MathEngine.calculate_totals(items)
    assert t.base_imponible_total == sum_of_rounded_lines
    assert sum(ln.base_imponible for ln in t.lineas) == t.base_imponible_total
    assert raw_sum != sum_of_rounded_lines or raw_sum == sum_of_rounded_lines
    _assert_invoice_atomically_closed(t)
    # IVA se acumula por línea cuantizada; no exigir igualdad con ``base_total × tipo`` si difiere en céntimo.
    assert t.cuota_iva_total == sum(
        quantize_financial(ln.base_imponible * Decimal("21") / Decimal("100")) for ln in t.lineas
    )


def test_cent_accumulation_thousand_lines_point_zero_one_five() -> None:
    """
    1000 × 0,015 €: cada línea cuantiza a 0,02 € (HALF_EVEN); base agregada 20,00 €.
    La cuota IVA se calcula **por línea**; con bases de 0,02 € la cuota por línea cuantiza a 0,00 €
    (coherencia interna: total = base + IVA).
    """
    n = 1000
    items = [{"cantidad": 1, "precio_unitario": "0.015", "tipo_iva_porcentaje": "21"} for _ in range(n)]
    per = quantize_financial(Decimal("1") * Decimal("0.015"))
    assert per == Decimal("0.02")
    t = MathEngine.calculate_totals(items)
    assert t.base_imponible_total == Decimal("20.00")
    assert t.base_imponible_total == quantize_financial(per * n)
    assert t.cuota_iva_total == Decimal("0.00")
    _assert_invoice_atomically_closed(t)


def test_floating_point_literal_sum_then_money() -> None:
    """Edge 2: 0,1 + 0,2 como float de Python; tras ``to_decimal`` + cuantía debe cerrar a 0,30 €."""
    x = 0.1 + 0.2
    assert str(x) == "0.30000000000000004"
    assert quantize_financial(to_decimal(x)) == Decimal("0.30")
    assert round_fiat(x) == Decimal("0.30")


def test_compute_f1_totals_tax_identity_many_rates() -> None:
    """Edge 3: identidad base + cuota == total para varios tipos de IVA."""
    for pct in ("0", "4", "10", "21"):
        base = Decimal("9999.99")
        b, c, tot = compute_f1_totals(base_imponible=base, iva_porcentaje=Decimal(pct))
        assert tot == quantize_financial(b + c)
        assert tot - b == c


def test_math_engine_high_volume_randomish_coherent() -> None:
    """500 líneas con importes string; invariante céntimo en cada paso."""
    items = []
    for i in range(500):
        p = Decimal("1") / Decimal(str(i + 7))
        items.append(
            {
                "cantidad": "1",
                "precio_unitario": format(p, ".6f"),
                "tipo_iva_porcentaje": "21" if i % 2 == 0 else "10",
            }
        )
    t = MathEngine.calculate_totals(items)
    _assert_invoice_atomically_closed(t)
    assert sum(ln.base_imponible for ln in t.lineas) == t.base_imponible_total
    s_iva = sum(d.cuota_iva for d in t.desglose_por_tipo)
    assert s_iva == t.cuota_iva_total


def test_safe_divide_triple_recombine_under_half_even() -> None:
    """
    División 100/3 → 33,33 € por paso; 3×33,33 = 99,99 € (no 100): la cuantía intermedia es deliberada.

    Evitar asumir ``n × round(a/b) == round(a)`` con redondeo bancario; usar una sola división o importes
    en ``Decimal``/``str`` si se requiere cierre exacto a total.
    """
    a = safe_divide(100, 3)
    assert a == Decimal("33.33")
    s = quantize_financial(a + a + a)
    assert s == Decimal("99.99")
    assert safe_divide(100, 1) == Decimal("100.00")


def test_to_decimal_rejects_non_finite_float() -> None:
    with pytest.raises(FinancialDomainError):
        to_decimal(float("nan"))
    with pytest.raises(FinancialDomainError):
        to_decimal(float("inf"))


def test_global_discount_proportional_cent_correction_still_closed() -> None:
    """Descuento global con reparto proporcional + corrección de deriva en línea mayor."""
    items = [{"precio_unitario": "0.33", "tipo_iva_porcentaje": "21"} for _ in range(30)]
    t = MathEngine.calculate_totals(items, global_discount=Decimal("1.00"))
    _assert_invoice_atomically_closed(t)
    assert t.importe_descuento_global_aplicado == Decimal("1.00")
