from __future__ import annotations

import logging
from typing import Any

import stripe
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.plans import PLAN_ENTERPRISE, PLAN_PRO, PLAN_STARTER, normalize_plan
from app.db.supabase import SupabaseAsync

logger = logging.getLogger(__name__)

# Suscripciones Stripe que bloquean acceso a la API (cuenta empresa “inactiva” para facturación).
_STRIPE_SUBSCRIPTION_INACTIVE: frozenset[str] = frozenset(
    {"canceled", "unpaid", "incomplete_expired", "paused"},
)


def _plan_to_price_id(plan_type: str) -> str:
    settings = get_settings()
    p = normalize_plan(plan_type)
    if p == PLAN_PRO:
        pid = settings.STRIPE_PRICE_PRO
    elif p == PLAN_ENTERPRISE:
        pid = settings.STRIPE_PRICE_ENTERPRISE
    else:
        pid = settings.STRIPE_PRICE_STARTER
    if not pid:
        raise RuntimeError(
            "Falta variable de entorno STRIPE_PRICE_STARTER / STRIPE_PRICE_PRO / STRIPE_PRICE_ENTERPRISE"
        )
    return pid


def _limite_vehiculos_for_plan(plan_normalized: str) -> int | None:
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return None
    if p == PLAN_PRO:
        return 25
    return 5


def _stripe_configured() -> bool:
    s = get_settings()
    return bool(s.STRIPE_SECRET_KEY and s.STRIPE_SECRET_KEY.strip())


def is_stripe_configured() -> bool:
    """True si ``STRIPE_SECRET_KEY`` está definida (Checkout / Portal disponibles)."""
    return _stripe_configured()


async def assert_empresa_billing_active(db: SupabaseAsync, *, empresa_id: str) -> None:
    """
    Comprueba que la empresa no esté archivada (``deleted_at``) y, si hay suscripción Stripe,
    que el estado en Stripe permita el uso del producto.

    Sin ``STRIPE_SECRET_KEY`` no se llama a la API de Stripe (desarrollo / despliegues sin billing).
    Sin ``stripe_subscription_id`` en la fila (p. ej. plan Starter sin tarjeta) se considera activo.
    """
    eid = str(empresa_id or "").strip()
    if not eid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Empresa no identificada",
        )

    try:
        res: Any = await db.execute(
            db.table("empresas")
            .select("deleted_at, stripe_subscription_id")
            .eq("id", eid)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception as exc:
        logger.warning("assert_empresa_billing_active: lectura empresas falló: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo verificar el estado de la empresa",
        ) from exc

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Empresa no encontrada",
        )

    row = rows[0]
    if row.get("deleted_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de empresa está archivada",
        )

    if not _stripe_configured():
        return

    sub_id = row.get("stripe_subscription_id")
    if sub_id is None or not str(sub_id).strip():
        return

    settings = get_settings()
    assert settings.STRIPE_SECRET_KEY is not None
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        sub = stripe.Subscription.retrieve(str(sub_id).strip())
    except stripe.error.StripeError as exc:
        logger.warning("Stripe Subscription.retrieve falló: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo verificar el estado de la suscripción",
        ) from exc

    st = str(getattr(sub, "status", None) or "").strip()
    if st in _STRIPE_SUBSCRIPTION_INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La suscripción de la empresa no está activa. Contacta con administración o renova la suscripción.",
        )


async def create_checkout_session(
    *,
    empresa_id: str,
    plan_type: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Crea una sesión de Stripe Checkout (modo suscripción) con ``client_reference_id`` = empresa UUID.
    """
    if not _stripe_configured():
        raise RuntimeError("Stripe no está configurado (STRIPE_SECRET_KEY)")

    settings = get_settings()
    assert settings.STRIPE_SECRET_KEY is not None
    stripe.api_key = settings.STRIPE_SECRET_KEY

    price_id = _plan_to_price_id(plan_type)
    pnorm = normalize_plan(plan_type)

    session = stripe.checkout.Session.create(
        mode="subscription",
        client_reference_id=str(empresa_id).strip(),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "empresa_id": str(empresa_id).strip(),
            "plan_type": pnorm,
        },
        subscription_data={
            "metadata": {
                "empresa_id": str(empresa_id).strip(),
                "plan_type": pnorm,
            }
        },
        allow_promotion_codes=True,
    )
    url = session.url
    if not url:
        raise RuntimeError("Stripe no devolvió URL de Checkout")
    return url


async def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """Portal de facturación Stripe (gestionar método de pago / cancelar)."""
    if not _stripe_configured():
        raise RuntimeError("Stripe no está configurado (STRIPE_SECRET_KEY)")

    settings = get_settings()
    assert settings.STRIPE_SECRET_KEY is not None
    stripe.api_key = settings.STRIPE_SECRET_KEY

    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    url = portal.url
    if not url:
        raise RuntimeError("Stripe no devolvió URL del portal")
    return url


async def _apply_subscription_to_empresa(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    plan_type: str,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
) -> None:
    pnorm = normalize_plan(plan_type)
    limite = _limite_vehiculos_for_plan(pnorm)
    payload: dict[str, Any] = {
        "plan": pnorm,
        "plan_type": pnorm,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "limite_vehiculos": limite,
    }
    await db.execute(
        db.table("empresas").update(payload).eq("id", str(empresa_id).strip())
    )
    logger.info(
        "empresa %s actualizada por Stripe: plan=%s limite=%s",
        empresa_id[:8],
        pnorm,
        limite,
    )


async def _downgrade_empresa_to_starter(
    db: SupabaseAsync,
    *,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> None:
    """Busca empresa por ids Stripe y la deja en plan Starter (equivalente a 'free' de producto)."""
    if stripe_subscription_id:
        res: Any = await db.execute(
            db.table("empresas")
            .select("id")
            .eq("stripe_subscription_id", stripe_subscription_id)
            .limit(1)
        )
    elif stripe_customer_id:
        res = await db.execute(
            db.table("empresas")
            .select("id")
            .eq("stripe_customer_id", stripe_customer_id)
            .limit(1)
        )
    else:
        return
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        logger.warning(
            "customer.subscription.deleted: ninguna empresa con sub=%s customer=%s",
            stripe_subscription_id,
            stripe_customer_id,
        )
        return

    eid = str(rows[0].get("id") or "").strip()
    if not eid:
        return

    payload = {
        "plan": PLAN_STARTER,
        "plan_type": PLAN_STARTER,
        "limite_vehiculos": 5,
        "stripe_subscription_id": None,
    }
    await db.execute(db.table("empresas").update(payload).eq("id", eid))
    logger.warning("empresa %s downgrade a Starter tras cancelación de suscripción", eid[:8])


async def handle_webhook(*, payload: bytes, sig_header: str | None, db: SupabaseAsync) -> dict[str, Any]:
    """
    Verifica firma HMAC de Stripe y procesa eventos relevantes.
    ``db`` debe ser cliente **service role** (bypass RLS) para actualizar ``empresas``.
    """
    settings = get_settings()
    wh_secret = settings.STRIPE_WEBHOOK_SECRET
    if not wh_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET no configurado")

    event = stripe.Webhook.construct_event(payload, sig_header or "", wh_secret)

    etype = event.get("type")
    data = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        sess = data
        modo = sess.get("mode")
        if modo != "subscription":
            return {"received": True, "ignored": "mode_not_subscription"}

        empresa_id = (sess.get("client_reference_id") or "").strip() or None
        meta = sess.get("metadata") or {}
        if not empresa_id:
            empresa_id = (meta.get("empresa_id") or "").strip() or None
        plan_type = (meta.get("plan_type") or PLAN_STARTER).strip()

        if not empresa_id:
            logger.error("checkout.session.completed sin empresa_id")
            return {"received": True, "error": "missing_empresa_id"}

        cust = sess.get("customer")
        if isinstance(cust, dict):
            cust = cust.get("id")
        sub = sess.get("subscription")
        if isinstance(sub, dict):
            sub = sub.get("id")

        await _apply_subscription_to_empresa(
            db,
            empresa_id=empresa_id,
            plan_type=plan_type,
            stripe_customer_id=str(cust) if cust else None,
            stripe_subscription_id=str(sub) if sub else None,
        )
        return {"received": True, "event": etype, "empresa_id": empresa_id}

    if etype == "customer.subscription.deleted":
        sub = data
        sub_id = str(sub.get("id") or "").strip() or None
        cust = sub.get("customer")
        if isinstance(cust, dict):
            cust = cust.get("id")
        cust_id = str(cust).strip() if cust else None

        await _downgrade_empresa_to_starter(
            db,
            stripe_subscription_id=sub_id,
            stripe_customer_id=cust_id,
        )
        return {"received": True, "event": etype}

    return {"received": True, "ignored": etype}
