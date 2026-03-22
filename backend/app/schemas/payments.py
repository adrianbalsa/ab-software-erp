from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PlanCheckoutLiteral = Literal["starter", "pro", "enterprise"]


class StripeCheckoutCreate(BaseModel):
    plan_type: PlanCheckoutLiteral = Field(
        ...,
        description="Plan SaaS a contratar (precio Stripe configurado por entorno)",
    )


class StripeCheckoutOut(BaseModel):
    url: str


class StripePortalOut(BaseModel):
    url: str
