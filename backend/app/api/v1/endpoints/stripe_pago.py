import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.config import settings

# Inicializamos el router y la llave secreta de Stripe
router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/crear-sesion-checkout")
async def crear_sesion_checkout(price_id: str, user_id: str):
    """
    Crea la sesión de pago y devuelve la URL segura de Stripe.
    """
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            # Redirecciones tras el pago (ajusta a tus rutas reales)
            success_url=f"{settings.FRONTEND_URL}/dashboard?pago=exito&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/precios?pago=cancelado",
            client_reference_id=user_id, # Fundamental para saber quién ha pagado
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Escucha las confirmaciones de pago de Stripe en segundo plano.
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
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
        
        # IMPORTANTE: Aquí llamas a la función que actualiza Supabase
        # Ejemplo conceptual:
        # db.marcar_usuario_como_premium(user_id)
        print(f"✅ Pago confirmado para el usuario: {user_id}")

    return {"status": "success"}