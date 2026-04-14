from __future__ import annotations

from os import getenv
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.core.config import get_settings
from app.schemas.payments import StripeCheckoutCreate, StripeCheckoutOut, StripePortalOut
from app.schemas.user import UserOut
from app.db.supabase import SupabaseAsync
from app.services import stripe_service

router = APIRouter()


def _checkout_urls() -> tuple[str, str]:
    settings = get_settings()
    base = (settings.PUBLIC_APP_URL or getenv("STRIPE_PUBLIC_APP_URL") or "http://localhost:3000").rstrip("/")
    success = getenv("STRIPE_SUCCESS_URL") or f"{base}/dashboard?checkout=success"
    cancel = getenv("STRIPE_CANCEL_URL") or f"{base}/?checkout=cancel"
    return success, cancel


@router.post("/create-checkout", response_model=StripeCheckoutOut)
async def create_checkout(
    body: StripeCheckoutCreate,
    current_user: UserOut = Depends(deps.require_admin_write_user),
) -> StripeCheckoutOut:
    """
    Inicia Stripe Checkout (suscripción). Solo **admin** del tenant.
    Devuelve la URL de pago.
    """
    if not stripe_service.is_stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pagos Stripe no configurados en el servidor",
        )
    success_url, cancel_url = _checkout_urls()
    try:
        url = await stripe_service.create_checkout_session(
            empresa_id=str(current_user.empresa_id),
            plan_type=body.plan_type,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    return StripeCheckoutOut(url=url)


async def _empresa_stripe_customer_id(db: SupabaseAsync, *, empresa_id: str) -> str | None:
    res: Any = await db.execute(
        db.table("empresas").select("stripe_customer_id").eq("id", empresa_id).limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        return None
    cid = rows[0].get("stripe_customer_id")
    return str(cid).strip() if cid else None


@router.post("/create-portal", response_model=StripePortalOut)
async def create_portal(
    current_user: UserOut = Depends(deps.require_admin_write_user),
    db: SupabaseAsync = Depends(deps.get_db),
) -> StripePortalOut:
    """Billing Portal de Stripe (cambiar tarjeta, cancelar). Requiere ``stripe_customer_id`` previo (tras checkout)."""
    if not stripe_service.is_stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pagos Stripe no configurados en el servidor",
        )
    eid = str(current_user.empresa_id)
    customer_id = await _empresa_stripe_customer_id(db, empresa_id=eid)
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La empresa no tiene cliente Stripe asociado. Completa un checkout primero.",
        )
    settings = get_settings()
    base = (settings.PUBLIC_APP_URL or getenv("STRIPE_PUBLIC_APP_URL") or "http://localhost:3000").rstrip("/")
    return_url = getenv("STRIPE_PORTAL_RETURN_URL") or f"{base}/dashboard?portal=return"
    try:
        url = await stripe_service.create_portal_session(
            customer_id=customer_id,
            return_url=return_url,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    return StripePortalOut(url=url)
