import stripe
from fastapi import APIRouter, HTTPException, Request

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
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            # Redirecciones tras el pago (ajusta a tus rutas reales)
            success_url=f"{_frontend_base()}/dashboard?pago=exito&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_frontend_base()}/precios?pago=cancelado",
            client_reference_id=user_id, # Fundamental para saber quién ha pagado
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/webhook",
    summary="Webhook de eventos Stripe (firma Stripe-Signature)",
)
async def stripe_webhook(request: Request):
    """
    Escucha las confirmaciones de pago de Stripe en segundo plano.
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    wh_secret = get_settings().STRIPE_WEBHOOK_SECRET or ""

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, wh_secret
        )
    except ValueError as e:
        # Payload inválido
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError as e:
        # Firma inválida (alguien intentando hackear el webhook)
        raise HTTPException(status_code=400, detail="Firma inválida")

    # Si el pago se ha completado con éxito
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        
        # Conexión con Supabase para actualizar el perfil (Indentación corregida)
        try:
            from app.db.supabase import get_supabase
            supabase = await get_supabase(allow_service_role_bypass=True)
            
            # Actualizamos la tabla de perfiles
            supabase.table("profiles").update({
                "subscription_status": "active",
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "plan_type": "pro" # Aquí mapearás en el futuro según el amount_total
            }).eq("id", user_id).execute()
            
            print(f"✅ Suscripción activada en Supabase para el usuario {user_id}")
        except Exception as e:
            print(f"❌ Error al actualizar Supabase: {str(e)}")

    return {"status": "success"}