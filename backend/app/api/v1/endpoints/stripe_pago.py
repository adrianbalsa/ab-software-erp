import stripe
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter()


def _frontend_base() -> str:
    return (get_settings().PUBLIC_APP_URL or "http://localhost:3000").rstrip("/")


@router.post(
    "/crear-sesion-checkout",
    summary="Crear sesión de checkout Stripe",
)
async def crear_sesion_checkout(price_id: str, user_id: str):
    """
    Crea la sesión de pago y devuelve la URL segura de Stripe.
    """
    cfg = get_settings()
    stripe.api_key = cfg.STRIPE_SECRET_KEY or ""
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{_frontend_base()}/dashboard?pago=exito&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_frontend_base()}/precios?pago=cancelado",
            client_reference_id=user_id,
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
