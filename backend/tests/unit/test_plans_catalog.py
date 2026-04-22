from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.plans import (
    EUR_MONTHLY_COMPLIANCE,
    EUR_MONTHLY_FINANCE,
    EUR_MONTHLY_FULL_STACK,
    ADDON_OCR_PACK,
    billing_addons,
    normalize_plan,
    plan_list_eur_monthly,
    plan_marketing_name,
)
from app.services import stripe_service
from app.services.stripe_service import _infer_base_plan_from_subscription_line_items


def test_normalize_plan_marketing_aliases() -> None:
    assert normalize_plan("COMPLIANCE") == "starter"
    assert normalize_plan("finance") == "pro"
    assert normalize_plan("full-stack") == "enterprise"
    assert normalize_plan("fullstack") == "enterprise"


def test_plan_marketing_and_list_prices() -> None:
    assert plan_marketing_name("starter") == "Compliance"
    assert plan_marketing_name("pro") == "Finance"
    assert plan_marketing_name("enterprise") == "Enterprise"
    assert plan_list_eur_monthly("compliance") == EUR_MONTHLY_COMPLIANCE
    assert plan_list_eur_monthly("finance") == EUR_MONTHLY_FINANCE
    assert plan_list_eur_monthly("full-stack") == EUR_MONTHLY_FULL_STACK


def test_billing_addons_catalog() -> None:
    slugs = {a.slug for a in billing_addons()}
    assert ADDON_OCR_PACK in slugs
    assert {a.eur_monthly for a in billing_addons() if a.slug == ADDON_OCR_PACK} == {15}


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
