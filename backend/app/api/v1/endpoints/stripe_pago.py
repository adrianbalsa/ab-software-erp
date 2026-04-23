from __future__ import annotations

from uuid import UUID

import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.plans import PLAN_ENTERPRISE, PLAN_STARTER
from app.services.secret_manager_service import get_secret_manager

router = APIRouter()


def _frontend_base() -> str:
    return (get_settings().PUBLIC_APP_URL or "http://localhost:3000").rstrip("/")


class StripeCheckoutPublicCreate(BaseModel):
    """Checkout público (landing): ``client_reference_id`` = empresa en Supabase."""

    price_id: str = Field(..., min_length=1)
    empresa_id: str = Field(..., min_length=1, description="UUID de public.empresas")


def _plan_slug_for_price_id(price_id: str) -> str:
    s = get_settings()
    pid = str(price_id or "").strip()
    ent = (s.STRIPE_PRICE_ENTERPRISE or "").strip()
    if ent and pid == ent:
        return PLAN_ENTERPRISE
    return PLAN_STARTER


@router.post(
    "/crear-sesion-checkout",
    summary="Crear sesión de checkout Stripe",
)
async def crear_sesion_checkout(body: StripeCheckoutPublicCreate) -> dict[str, str | None]:
    """
    Crea Checkout (suscripción) con ``client_reference_id`` = ``empresa_id`` y metadata de plan
    para el webhook ``checkout.session.completed``.
    """
    try:
        UUID(str(body.empresa_id).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="empresa_id debe ser un UUID válido") from exc

    sk = get_secret_manager().get_stripe_secret_key() or ""
    if not str(sk).strip():
        raise HTTPException(status_code=503, detail="Stripe no está configurado en el servidor")

    stripe.api_key = sk
    eid = str(body.empresa_id).strip()
    plan_slug = _plan_slug_for_price_id(body.price_id)
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": str(body.price_id).strip(), "quantity": 1}],
            mode="subscription",
            success_url=f"{_frontend_base()}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_frontend_base()}/pricing?checkout=cancel",
            client_reference_id=eid,
            metadata={"empresa_id": eid, "plan_type": plan_slug},
            subscription_data={"metadata": {"empresa_id": eid, "plan_type": plan_slug}},
            allow_promotion_codes=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"url": checkout_session.url}
