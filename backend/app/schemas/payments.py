from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PlanCheckoutLiteral = Literal[
    "starter",
    "pro",
    "enterprise",
    "compliance",
    "finance",
    "full-stack",
    "fullstack",
]


class StripeCheckoutCreate(BaseModel):
    plan_type: PlanCheckoutLiteral = Field(
        ...,
        description=(
            "Plan SaaS a contratar (slug canónico: starter/pro/enterprise). "
            "Alias comerciales: compliance→starter, finance→pro, full-stack|fullstack→enterprise. "
            "Los price_id de Stripe se definen en entorno (p. ej. STRIPE_PRICE_COMPLIANCE o STRIPE_PRICE_STARTER)."
        ),
    )


class StripeCheckoutOut(BaseModel):
    url: str


class StripePortalOut(BaseModel):
    url: str
