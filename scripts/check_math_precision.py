#!/usr/bin/env python3
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


MONEY_QUANT = Decimal("0.01")


def q(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def check_sum_lines() -> tuple[bool, Decimal, Decimal]:
    line = Decimal("0.10")
    result = sum((line for _ in range(100)), start=Decimal("0.00"))
    result_q = q(result)
    expected = Decimal("10.00")
    return result_q == expected, result_q, expected


def check_discount_vat() -> dict[str, object]:
    price = Decimal("19.99")
    discount_pct = Decimal("15")
    vat_pct = Decimal("21")

    discount_amount = q(price * (discount_pct / Decimal("100")))
    base_after_discount = q(price - discount_amount)
    vat_amount = q(base_after_discount * (vat_pct / Decimal("100")))
    total = q(base_after_discount + vat_amount)

    expected_total = Decimal("20.56")
    ok = total == expected_total
    return {
        "ok": ok,
        "price": price,
        "discount_amount": discount_amount,
        "base_after_discount": base_after_discount,
        "vat_amount": vat_amount,
        "total": total,
        "expected_total": expected_total,
    }


def check_float_artifacts() -> tuple[bool, str]:
    # Simulación deliberada de cálculo con float para detectar artefactos binarios.
    float_sum = 0.0
    for _ in range(100):
        float_sum += 0.10

    f_price = 19.99
    f_discounted = f_price * (1 - 0.15)
    f_total = f_discounted * 1.21

    trace = (
        f"float_sum={float_sum!r}, "
        f"f_discounted={f_discounted!r}, "
        f"f_total={f_total!r}"
    )
    has_artifact = "999999" in trace or "000001" in trace
    return (not has_artifact), trace


def main() -> int:
    ok_lines, lines_result, lines_expected = check_sum_lines()
    discount_report = check_discount_vat()
    ok_float, float_trace = check_float_artifacts()

    print("=== Math Precision Check (ROUND_HALF_UP, 2 decimales) ===")
    print(f"[1] 100 x 0.10 => {lines_result} (esperado {lines_expected})")
    print(
        "[2] 19.99 con -15% y +21% IVA => "
        f"base={discount_report['base_after_discount']} "
        f"iva={discount_report['vat_amount']} "
        f"total={discount_report['total']} "
        f"(esperado {discount_report['expected_total']})"
    )
    print(f"[3] Traza float (artefactos binarios): {float_trace}")

    ok_all = bool(ok_lines and discount_report["ok"])
    if ok_all:
        print("RESULTADO: PASS")
        if not ok_float:
            print(
                "WARN: se detectan artefactos binarios con float; "
                "mantener Decimal en todo el flujo monetario."
            )
        return 0

    print("RESULTADO: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
