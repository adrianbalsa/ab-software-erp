"""Webhook Stripe: firma ``Stripe-Signature`` y ``STRIPE_WEBHOOK_SECRET`` vía ``SecretManagerService``."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.services import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/stripe")
@router.post(
    "/payments/stripe/webhook",
    summary="Alias legacy del webhook Stripe",
    description="Misma lógica que ``POST /api/v1/webhooks/stripe``. Configurar solo un endpoint en Stripe Dashboard.",
)
async def stripe_webhook(
    request: Request,
    db: SupabaseAsync = Depends(deps.get_db_admin),
) -> JSONResponse:
    """
    Eventos Stripe: ``checkout.session.completed``, ``invoice.paid``, ``invoice.payment_failed``,
    ``customer.subscription.*``, etc.

    **checkout.session.completed** (modo ``subscription``):

    - Lee ``client_reference_id`` / metadata ``empresa_id`` y actualiza ``empresas.stripe_subscription_id``,
      ``plan_type``, ``subscription_status`` y ``plan_status`` (vía ``stripe_service``).
    - Plan **Enterprise**: extrae email del comprador y envía bienvenida con ``EmailService``;
      si el correo falla, se registra en Sentry con ``op=stripe.webhook`` y ``name=onboarding_email_failed``
      sin alterar la respuesta **200** a Stripe (reintentos del proveedor).

    La verificación HMAC usa ``stripe.Webhook.construct_event`` con el secreto del endpoint
    (``get_secret_manager().get_stripe_webhook_secret()`` → ``STRIPE_WEBHOOK_SECRET`` en env).
    """
    sig = request.headers.get("Stripe-Signature")
    payload = await request.body()

    try:
        result = await stripe_service.handle_webhook(payload=payload, sig_header=sig, db=db)
    except RuntimeError as e:
        logger.warning("webhook stripe: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.warning("webhook stripe payload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload inválido",
        ) from e
    except Exception as e:
        mod = getattr(e, "__module__", "") or ""
        if mod.startswith("stripe"):
            logger.warning("webhook stripe SDK: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Firma o evento inválido",
            ) from e
        raise

    if isinstance(result, dict) and result.get("duplicate"):
        logger.info(
            "stripe webhook idempotent replay ignored event_id=%s",
            result.get("event_id") or "-",
        )

    if isinstance(result, dict) and result.get("event") == "checkout.session.completed":
        logger.info(
            "stripe webhook checkout completado empresa_id=%s",
            result.get("empresa_id"),
        )

    return JSONResponse(content=result)
