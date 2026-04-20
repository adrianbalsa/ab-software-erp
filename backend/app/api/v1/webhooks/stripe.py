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


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: SupabaseAsync = Depends(deps.get_db_admin),
) -> JSONResponse:
    """
    Eventos Stripe: ``invoice.paid``, ``invoice.payment_failed``, ``customer.subscription.deleted``, etc.

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

    return JSONResponse(content=result)
