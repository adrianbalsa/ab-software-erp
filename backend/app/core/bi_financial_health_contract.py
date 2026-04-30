"""
Contrato de coherencia para ``GET /api/v1/bi/financial-health`` (DD §2.3).

Valida que los totales en ``meta`` y el ``summary`` cuadren con la suma de ``series``
y con ``FinancialAggregator`` (misma semántica que ``BiService.get_company_financial_health``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.math_engine import FinancialAggregator, quantize_currency


def _dec(x: Any) -> Decimal:
    try:
        return Decimal(str(x or 0))
    except Exception:
        return Decimal("0")


def financial_health_coherence_issues(
    *,
    summary: dict[str, Any],
    series: list[dict[str, Any]],
    meta: dict[str, Any],
    tol_eur: Decimal = Decimal("0.05"),
    tol_pct: Decimal = Decimal("0.02"),
) -> list[str]:
    """
    Lista vacía si la respuesta es coherente; en caso contrario, mensajes de diagnóstico.
    """
    issues: list[str] = []

    tot_ing = sum(_dec(p.get("ingresos")) for p in series)
    tot_gas = sum(_dec(p.get("gastos")) for p in series)
    tot_co2_cost = sum(_dec(p.get("co2_cost")) for p in series)

    meta_ing = _dec(meta.get("ingresos_operativos"))
    meta_gas = _dec(meta.get("costes_operativos"))
    meta_co2 = _dec(meta.get("costo_carbono_total"))

    if abs(tot_ing - meta_ing) > tol_eur:
        issues.append(f"ingresos: suma serie {tot_ing} ≠ meta.ingresos_operativos {meta_ing}")
    if abs(tot_gas - meta_gas) > tol_eur:
        issues.append(f"gastos: suma serie {tot_gas} ≠ meta.costes_operativos {meta_gas}")
    if abs(tot_co2_cost - meta_co2) > tol_eur:
        issues.append(f"co2_cost: suma serie {tot_co2_cost} ≠ meta.costo_carbono_total {meta_co2}")

    ebitda_expected = FinancialAggregator.calculate_ebitda_bruto(
        ingresos_operativos=tot_ing,
        costes_operativos=tot_gas,
    )
    ebitda_api = _dec(summary.get("ebitda"))
    if abs(ebitda_expected - ebitda_api) > tol_eur:
        issues.append(f"ebitda: agregado {ebitda_expected} ≠ summary.ebitda {ebitda_api}")

    margin_expected = FinancialAggregator.calculate_margen_operativo(
        ebitda_bruto=ebitda_expected,
        ventas=tot_ing,
    )
    margin_api = _dec(summary.get("operating_margin_pct"))
    if abs(margin_expected - margin_api) > tol_pct:
        issues.append(f"margen %: calculado {margin_expected} ≠ summary {margin_api}")

    saldo = meta.get("saldo_facturas_emitidas_eur")
    if saldo is not None:
        cf_expected = FinancialAggregator.calculate_cash_flow_estimado(
            saldo_facturas_emitidas=_dec(saldo),
            gastos_registrados=tot_gas,
        )
        cf_api = _dec(summary.get("cash_flow"))
        if abs(cf_expected - cf_api) > tol_eur:
            issues.append(f"cash_flow: calculado {cf_expected} ≠ summary {cf_api}")

    return issues


def assert_financial_health_coherent(payload: dict[str, Any]) -> None:
    """Pytest-friendly: lanza AssertionError si hay descuadres."""
    issues = financial_health_coherence_issues(
        summary=dict(payload.get("summary") or {}),
        series=list(payload.get("series") or []),
        meta=dict(payload.get("meta") or {}),
    )
    if issues:
        raise AssertionError("; ".join(issues))
