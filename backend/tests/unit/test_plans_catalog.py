from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.plans import (
    COMPLIANCE_MAX_FACTURAS_MES,
    EUR_MONTHLY_ENTERPRISE,
    EUR_MONTHLY_ESSENTIAL,
    EUR_MONTHLY_PRO,
    ADDON_OCR_PACK,
    CostMeter,
    billing_addons,
    max_facturas_mes,
    max_workspace_seats,
    monthly_cost_quota,
    monthly_cost_quotas,
    normalize_plan,
    plan_list_eur_monthly,
    plan_marketing_name,
)
from app.services import stripe_service
from app.services.stripe_service import _infer_base_plan_from_subscription_line_items


def test_normalize_plan_marketing_aliases() -> None:
    assert normalize_plan("COMPLIANCE") == "starter"
    assert normalize_plan("essential") == "starter"
    assert normalize_plan("finance") == "pro"
    assert normalize_plan("operational") == "pro"
    assert normalize_plan("institutional") == "enterprise"
    assert normalize_plan("full-stack") == "enterprise"
    assert normalize_plan("fullstack") == "enterprise"


def test_plan_marketing_and_list_prices() -> None:
    assert plan_marketing_name("starter") == "Compliance"
    assert plan_marketing_name("pro") == "Operational"
    assert plan_marketing_name("enterprise") == "Institutional"
    assert plan_list_eur_monthly("compliance") == EUR_MONTHLY_ESSENTIAL
    assert plan_list_eur_monthly("finance") == EUR_MONTHLY_PRO
    assert plan_list_eur_monthly("full-stack") == EUR_MONTHLY_ENTERPRISE


def test_workspace_seat_limits_align_with_fleet_tiers() -> None:
    assert max_workspace_seats("starter") == 5
    assert max_workspace_seats("pro") == 30
    assert max_workspace_seats("enterprise") is None


def test_compliance_monthly_invoice_cap_only_on_starter() -> None:
    assert max_facturas_mes("starter") == COMPLIANCE_MAX_FACTURAS_MES
    assert max_facturas_mes("pro") is None
    assert max_facturas_mes("enterprise") is None


def test_billing_addons_catalog() -> None:
    slugs = {a.slug for a in billing_addons()}
    assert ADDON_OCR_PACK in slugs
    assert {a.eur_monthly for a in billing_addons() if a.slug == ADDON_OCR_PACK} == {15}


def test_monthly_cost_quotas_increase_by_plan() -> None:
    starter = {q.meter: q.limit_units for q in monthly_cost_quotas("starter")}
    pro = {q.meter: q.limit_units for q in monthly_cost_quotas("finance")}
    enterprise = {q.meter: q.limit_units for q in monthly_cost_quotas("enterprise")}

    assert starter[CostMeter.MAPS] < pro[CostMeter.MAPS] < enterprise[CostMeter.MAPS]
    assert starter[CostMeter.OCR] < pro[CostMeter.OCR] < enterprise[CostMeter.OCR]
    assert starter[CostMeter.AI] < pro[CostMeter.AI] < enterprise[CostMeter.AI]
    assert monthly_cost_quota("starter", CostMeter.OCR).unit_label == "páginas"
    assert monthly_cost_quota("starter", "ocr").meter == CostMeter.OCR


@pytest.mark.parametrize(
    "order",
    [
        ["price_ocr", "price_starter"],
        ["price_starter", "price_ocr"],
    ],
)
def test_infer_base_plan_ignores_addon_line_order(
    monkeypatch: pytest.MonkeyPatch, order: list[str]
) -> None:
    settings = MagicMock()
    settings.STRIPE_PRICE_ENTERPRISE = None
    settings.STRIPE_PRICE_PRO = None
    settings.STRIPE_PRICE_STARTER = "price_starter"
    settings.STRIPE_PRICE_OCR_PACK = "price_ocr"
    settings.STRIPE_PRICE_WEBHOOKS_B2B_PREMIUM = None
    settings.STRIPE_PRICE_LOGISADVISOR_IA_PRO = None

    items_data = []
    for pid in order:
        items_data.append({"price": {"id": pid}})

    sub = {"items": {"data": items_data}}

    monkeypatch.setattr(stripe_service, "get_settings", lambda: settings)
    assert _infer_base_plan_from_subscription_line_items(sub) == "starter"
