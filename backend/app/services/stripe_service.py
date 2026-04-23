from __future__ import annotations

import logging
from typing import Any

import stripe
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.services.secret_manager_service import get_secret_manager
from app.services.webhook_idempotency import (
    claim_webhook_event,
    finalize_stripe_webhook_claim,
    release_stripe_webhook_claim,
)
from app.core.plans import PLAN_ENTERPRISE, PLAN_PRO, PLAN_STARTER, normalize_plan
from app.db.supabase import SupabaseAsync
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# Suscripciones Stripe que bloquean acceso a la API (cuenta empresa “inactiva” para facturación).
_STRIPE_SUBSCRIPTION_INACTIVE: frozenset[str] = frozenset(
    {"canceled", "unpaid", "incomplete_expired", "paused"},
)


def _checkout_session_customer_email(sess: dict[str, Any]) -> str | None:
    cd = sess.get("customer_details")
    if isinstance(cd, dict):
        raw = cd.get("email")
        if raw and str(raw).strip():
            return str(raw).strip()
    raw = sess.get("customer_email")
    if raw and str(raw).strip():
        return str(raw).strip()
    return None


def _sentry_onboarding_email_failed(*, empresa_id: str, detail: str) -> None:
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_context("stripe_checkout", {"empresa_id": empresa_id, "detail": detail})
            with sentry_sdk.start_span(op="stripe.webhook", name="onboarding_email_failed"):
                sentry_sdk.capture_message("onboarding_email_failed", level="error")
    except Exception:
        pass


async def _send_enterprise_welcome_after_checkout(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    customer_email: str | None,
) -> None:
    """No lanza: fallos → log + Sentry (op ``stripe.webhook``); la respuesta HTTP a Stripe sigue siendo 200."""
    em = (customer_email or "").strip()
    if not em:
        _sentry_onboarding_email_failed(empresa_id=empresa_id, detail="missing_customer_email")
        return
    try:
        res: Any = await db.execute(
            db.table("empresas")
            .select("nombre_comercial,nombre_legal")
            .eq("id", str(empresa_id).strip())
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception as exc:
        logger.warning("welcome enterprise: lectura empresa falló: %s", exc)
        _sentry_onboarding_email_failed(empresa_id=empresa_id, detail=f"db_read:{exc!s}")
        return
    if not rows:
        _sentry_onboarding_email_failed(empresa_id=empresa_id, detail="empresa_not_found")
        return
    row = rows[0]
    company = str(row.get("nombre_comercial") or row.get("nombre_legal") or "").strip() or "AB Logistics OS"
    try:
        ok = EmailService().send_welcome_enterprise(em, company)
    except Exception as exc:
        logger.exception("welcome enterprise: excepción inesperada: %s", exc)
        _sentry_onboarding_email_failed(empresa_id=empresa_id, detail=f"exception:{exc!s}")
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return
    if not ok:
        _sentry_onboarding_email_failed(empresa_id=empresa_id, detail="send_returned_false")


def _subscription_object_to_dict(sub_obj: Any) -> dict[str, Any]:
    if isinstance(sub_obj, dict):
        return sub_obj
    fn = getattr(sub_obj, "to_dict", None)
    if callable(fn):
        try:
            out = fn()
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    return {}


def _price_id_to_plan(price_id: str | None) -> str | None:
    """Mapea el price id de Stripe al plan normalizado, si coincide con variables de entorno."""
    if not price_id or not str(price_id).strip():
        return None
    pid = str(price_id).strip()
    settings = get_settings()
    mapping: list[tuple[str, str | None]] = [
        (PLAN_ENTERPRISE, settings.STRIPE_PRICE_ENTERPRISE),
        (PLAN_PRO, settings.STRIPE_PRICE_PRO),
        (PLAN_STARTER, settings.STRIPE_PRICE_BASIC),
        (PLAN_STARTER, settings.STRIPE_PRICE_STARTER),
    ]
    for plan, env_pid in mapping:
        if env_pid and pid == str(env_pid).strip():
            return plan
    return None


def _addon_price_ids_normalized(settings: Settings) -> frozenset[str]:
    """Price IDs configurados para add-ons (no determinan el plan base)."""
    raw: list[str | None] = [
        settings.STRIPE_PRICE_OCR_PACK,
        settings.STRIPE_PRICE_WEBHOOKS_B2B_PREMIUM,
        settings.STRIPE_PRICE_LOGISADVISOR_IA_PRO,
    ]
    out: set[str] = set()
    for x in raw:
        if x and str(x).strip():
            out.add(str(x).strip())
    return frozenset(out)


def _item_price_id(item: dict[str, Any]) -> str | None:
    price = item.get("price")
    if isinstance(price, str):
        return price.strip() or None
    if isinstance(price, dict):
        raw = price.get("id")
        return str(raw).strip() if raw else None
    return None


def _all_subscription_price_ids(sub_obj: dict[str, Any]) -> list[str]:
    """Todos los price id activos en la suscripción (base + add-ons)."""
    items = sub_obj.get("items")
    if not isinstance(items, dict):
        return []
    data = items.get("data") or []
    out: list[str] = []
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        pid = _item_price_id(row)
        if pid:
            out.append(pid)
    return out


def _infer_base_plan_from_subscription_line_items(sub_obj: dict[str, Any]) -> str | None:
    """
    Determina el plan SaaS cuando hay varias líneas (plan base + add-ons Stripe).
    Prioridad: Enterprise > Pro > Starter si varios price de plan coinciden (caso anómalo).
    """
    settings = get_settings()
    price_ids = {p.strip() for p in _all_subscription_price_ids(sub_obj) if p and str(p).strip()}
    if not price_ids:
        return None
    candidates: list[tuple[int, str]] = []
    tier: list[tuple[int, str, str | None]] = [
        (3, PLAN_ENTERPRISE, settings.STRIPE_PRICE_ENTERPRISE),
        (2, PLAN_PRO, settings.STRIPE_PRICE_PRO),
        (1, PLAN_STARTER, settings.STRIPE_PRICE_BASIC),
        (1, PLAN_STARTER, settings.STRIPE_PRICE_STARTER),
    ]
    for prio, plan, env_pid in tier:
        if env_pid and str(env_pid).strip() in price_ids:
            candidates.append((prio, plan))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


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
            "Falta variable de entorno para el price del plan: "
            "STRIPE_PRICE_STARTER (o STRIPE_PRICE_COMPLIANCE), "
            "STRIPE_PRICE_PRO (o STRIPE_PRICE_FINANCE), "
            "STRIPE_PRICE_ENTERPRISE (o STRIPE_PRICE_FULL_STACK)"
        )
    return pid


async def _empresa_id_for_stripe_customer(
    db: SupabaseAsync, *, stripe_customer_id: str
) -> str | None:
    cid = str(stripe_customer_id or "").strip()
    if not cid:
        return None
    try:
        res: Any = await db.execute(
            db.table("empresas")
            .select("id")
            .eq("stripe_customer_id", cid)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception as exc:
        logger.warning("lookup empresa por stripe_customer_id: %s", exc)
        return None
    if not rows:
        return None
    return str(rows[0].get("id") or "").strip() or None


async def _merge_empresa_billing_fields(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    fields: dict[str, Any],
) -> None:
    if not fields:
        return
    await db.execute(db.table("empresas").update(dict(fields)).eq("id", str(empresa_id).strip()))


def _limite_vehiculos_for_plan(plan_normalized: str) -> int | None:
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return None
    if p == PLAN_PRO:
        return 25
    return 5


def _stripe_configured() -> bool:
    sk = get_secret_manager().get_stripe_secret_key()
    return bool(sk and sk.strip())


def is_stripe_configured() -> bool:
    """True si ``STRIPE_SECRET_KEY`` está definida (Checkout / Portal disponibles)."""
    return _stripe_configured()


async def assert_empresa_billing_active(db: SupabaseAsync, *, empresa_id: str) -> None:
    """
    Comprueba que la empresa no esté archivada (``deleted_at``) y, si hay suscripción Stripe,
    que el estado en Stripe permita el uso del producto.

    Sin ``STRIPE_SECRET_KEY`` no se llama a la API de Stripe (desarrollo / despliegues sin billing).
    Sin ``stripe_subscription_id`` en la fila (p. ej. plan Compliance sin tarjeta) se considera activo.
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
            .select("deleted_at, stripe_subscription_id, is_active")
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

    if row.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de empresa está suspendida por facturación. Actualiza el método de pago o contacta con administración.",
        )

    if not _stripe_configured():
        return

    sub_id = row.get("stripe_subscription_id")
    if sub_id is None or not str(sub_id).strip():
        return

    sk = get_secret_manager().get_stripe_secret_key()
    assert sk is not None
    stripe.api_key = sk

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

    sk = get_secret_manager().get_stripe_secret_key()
    assert sk is not None
    stripe.api_key = sk

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

    sk = get_secret_manager().get_stripe_secret_key()
    assert sk is not None
    stripe.api_key = sk

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
        "subscription_status": "active",
        "plan_status": "active",
        "is_active": True,
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
    """Busca empresa por ids Stripe y la deja en plan Compliance (slug `starter`)."""
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
        "subscription_status": "canceled",
        "plan_status": "canceled",
        "is_active": True,
    }
    await db.execute(db.table("empresas").update(payload).eq("id", eid))
    logger.warning("empresa %s downgrade a Compliance (starter) tras cancelación de suscripción", eid[:8])


def _stripe_external_event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("id") or "").strip()
    eid = getattr(event, "id", None)
    if eid is not None and str(eid).strip():
        return str(eid).strip()
    if hasattr(event, "get"):
        try:
            return str(event.get("id") or "").strip()
        except Exception:
            return ""
    return ""


async def _dispatch_stripe_webhook_event(db: SupabaseAsync, event: Any) -> dict[str, Any]:
    etype = event.get("type") if hasattr(event, "get") else getattr(event, "type", None)
    data_obj = event.get("data", {}) if hasattr(event, "get") else getattr(event, "data", {}) or {}
    if not isinstance(data_obj, dict):
        data_obj = {}
    data = data_obj.get("object", {})
    if not isinstance(data, dict):
        data = {}

    if etype == "checkout.session.completed":
        sess = data
        modo = sess.get("mode")
        if modo != "subscription":
            return {"received": True, "ignored": "mode_not_subscription"}

        empresa_id = (sess.get("client_reference_id") or "").strip() or None
        meta = sess.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        if not empresa_id:
            empresa_id = (meta.get("empresa_id") or "").strip() or None
        raw_meta_plan = str(meta.get("plan_type") or "").strip()
        if raw_meta_plan:
            plan_type = normalize_plan(raw_meta_plan)
        else:
            plan_type = normalize_plan(PLAN_STARTER)
            sub_probe = sess.get("subscription")
            if isinstance(sub_probe, dict):
                sub_probe = sub_probe.get("id")
            if sub_probe and _stripe_configured():
                sk = get_secret_manager().get_stripe_secret_key()
                if sk and str(sk).strip():
                    stripe.api_key = sk
                    try:
                        sub_obj = stripe.Subscription.retrieve(str(sub_probe))
                        mapped = _infer_base_plan_from_subscription_line_items(
                            _subscription_object_to_dict(sub_obj)
                        )
                        if mapped:
                            plan_type = normalize_plan(mapped)
                    except Exception as exc:
                        logger.warning("checkout.session.completed: inferir plan desde subscription: %s", exc)

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
        if normalize_plan(plan_type) == PLAN_ENTERPRISE:
            await _send_enterprise_welcome_after_checkout(
                db,
                empresa_id=empresa_id,
                customer_email=_checkout_session_customer_email(sess),
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

    if etype == "invoice.paid":
        inv = data
        cust = inv.get("customer")
        if isinstance(cust, dict):
            cust = cust.get("id")
        sub = inv.get("subscription")
        if isinstance(sub, dict):
            sub = sub.get("id")
        cid = str(cust).strip() if cust else ""
        if cid:
            eid = await _empresa_id_for_stripe_customer(db, stripe_customer_id=cid)
            if eid:
                fields: dict[str, Any] = {
                    "subscription_status": "active",
                    "plan_status": "active",
                    "is_active": True,
                }
                if sub:
                    fields["stripe_subscription_id"] = str(sub).strip()
                await _merge_empresa_billing_fields(db, empresa_id=eid, fields=fields)
        settings = get_settings()
        addons = _addon_price_ids_normalized(settings)
        logger.info(
            "invoice.paid customer=%s subscription=%s amount_paid=%s currency=%s addon_prices_configured=%s",
            cust,
            sub,
            inv.get("amount_paid"),
            inv.get("currency"),
            bool(addons),
        )
        return {"received": True, "event": etype}

    if etype == "invoice.payment_failed":
        inv = data
        cust = inv.get("customer")
        if isinstance(cust, dict):
            cust = cust.get("id")
        cid = str(cust).strip() if cust else ""
        if not cid:
            logger.error("invoice.payment_failed sin customer")
            return {"received": True, "error": "missing_customer"}
        eid = await _empresa_id_for_stripe_customer(db, stripe_customer_id=cid)
        if not eid:
            logger.warning("invoice.payment_failed: ninguna empresa para customer=%s", cid)
            return {"received": True, "ignored": "unknown_customer"}
        await _merge_empresa_billing_fields(
            db,
            empresa_id=eid,
            fields={
                "subscription_status": "past_due",
                "plan_status": "past_due",
                "is_active": False,
            },
        )
        logger.warning(
            "invoice.payment_failed: empresa %s suspendida (past_due)",
            eid[:8],
        )
        return {"received": True, "event": etype, "empresa_id": eid}

    if etype == "customer.subscription.updated":
        sub = data
        st = str(sub.get("status") or "").strip()
        if st in _STRIPE_SUBSCRIPTION_INACTIVE:
            return {"received": True, "ignored": "subscription_inactive"}

        meta = sub.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        empresa_id = str(meta.get("empresa_id") or "").strip() or None
        sub_id = str(sub.get("id") or "").strip() or None

        if not empresa_id and sub_id:
            try:
                res_sub: Any = await db.execute(
                    db.table("empresas")
                    .select("id")
                    .eq("stripe_subscription_id", sub_id)
                    .limit(1)
                )
                rows_sub: list[dict[str, Any]] = (
                    (res_sub.data or []) if hasattr(res_sub, "data") else []
                )
            except Exception as exc:
                logger.warning("subscription.updated: lookup empresa por sub falló: %s", exc)
                rows_sub = []
            if rows_sub:
                empresa_id = str(rows_sub[0].get("id") or "").strip() or None

        if not empresa_id:
            logger.warning("customer.subscription.updated sin empresa_id (sub=%s)", sub_id)
            return {"received": True, "ignored": "missing_empresa_id"}

        mapped = _infer_base_plan_from_subscription_line_items(sub)
        if not mapped:
            for pid in _all_subscription_price_ids(sub):
                mapped = _price_id_to_plan(pid)
                if mapped:
                    break
        meta_plan = str(meta.get("plan_type") or "").strip()
        if mapped:
            plan_type = normalize_plan(mapped)
        elif meta_plan:
            plan_type = normalize_plan(meta_plan)
        else:
            logger.info(
                "customer.subscription.updated: sin price mapeable ni plan_type en metadata (sub=%s); no actualizamos plan",
                sub_id,
            )
            return {"received": True, "ignored": "no_plan_signal"}

        cust = sub.get("customer")
        if isinstance(cust, dict):
            cust = cust.get("id")

        await _apply_subscription_to_empresa(
            db,
            empresa_id=empresa_id,
            plan_type=plan_type,
            stripe_customer_id=str(cust) if cust else None,
            stripe_subscription_id=sub_id,
        )
        return {"received": True, "event": etype, "empresa_id": empresa_id}

    return {"received": True, "ignored": etype}


async def handle_webhook(*, payload: bytes, sig_header: str | None, db: SupabaseAsync) -> dict[str, Any]:
    """
    Verifica firma HMAC de Stripe (``stripe.Webhook.construct_event`` + secreto vía ``get_secret_manager()``)
    y procesa eventos relevantes.
    ``db`` debe ser cliente **service role** (bypass RLS) para actualizar ``empresas``.

    Idempotencia: si el evento incluye ``id`` (evt_…), se registra en ``webhook_events``;
    entregas duplicadas de Stripe devuelven ``{"received": True, "duplicate": True}`` sin repetir
    efectos en ``empresas``. Si el procesamiento falla, se libera el claim para permitir reintento.
    """
    wh_secret = get_secret_manager().get_stripe_webhook_secret()
    if not wh_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET no configurado")

    event = stripe.Webhook.construct_event(payload, sig_header or "", wh_secret)
    event_id = _stripe_external_event_id(event)
    etype_raw = event.get("type") if hasattr(event, "get") else getattr(event, "type", None)
    etype_str = str(etype_raw or "").strip()

    claim_made = False
    if event_id:
        claim_made = await claim_webhook_event(
            db,
            provider="stripe",
            external_event_id=event_id,
            event_type=etype_str or "unknown",
            payload={"id": event_id, "type": etype_str},
            status="PROCESSING",
        )
        if not claim_made:
            return {"received": True, "duplicate": True}

    try:
        result = await _dispatch_stripe_webhook_event(db, event)
        if claim_made and event_id:
            await finalize_stripe_webhook_claim(db, external_event_id=event_id)
        return result
    except Exception:
        if claim_made and event_id:
            await release_stripe_webhook_claim(db, external_event_id=event_id)
        raise
