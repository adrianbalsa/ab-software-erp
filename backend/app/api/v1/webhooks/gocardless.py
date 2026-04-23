from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from starlette.responses import Response

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.services.email_service import EmailService
from app.services.secret_manager_service import get_secret_manager
from app.services.webhook_idempotency import claim_webhook_event

router = APIRouter()
_log = logging.getLogger(__name__)


def _capture_gocardless_error(
    *,
    message: str,
    level: str = "error",
    exc: BaseException | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("provider", "gocardless")
            scope.set_tag("op", "payments.gocardless")
            if extra:
                scope.set_context("gocardless", extra)
            if exc is not None:
                sentry_sdk.capture_exception(exc)
            else:
                sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass


def _extract_event_type(event: dict[str, Any]) -> str:
    resource_type = str(event.get("resource_type") or "").strip().lower()
    action = str(event.get("action") or "").strip().lower()
    if resource_type and action:
        return f"{resource_type}.{action}"
    raw = str(event.get("event_type") or "").strip().lower()
    return raw


def _build_gocardless_client() -> Any:
    mgr = get_secret_manager()
    token = mgr.get_gocardless_access_token()
    if not token:
        raise RuntimeError("GoCardless no configurado (falta GOCARDLESS_ACCESS_TOKEN).")
    import gocardless_pro

    return gocardless_pro.Client(
        access_token=token,
        environment=mgr.get_gocardless_env(),
    )


async def _process_billing_request_fulfilled(
    *,
    db: SupabaseAsync,
    event: dict[str, Any],
) -> None:
    links = event.get("links") if isinstance(event.get("links"), dict) else {}
    billing_request_id = str((links or {}).get("billing_request") or "").strip()
    if not billing_request_id:
        return

    try:
        gc_client = _build_gocardless_client()
        billing_request = await asyncio.to_thread(
            lambda: gc_client.billing_requests.get(billing_request_id)
        )
    except Exception as exc:
        _capture_gocardless_error(
            message="gocardless_billing_request_get_failed",
            exc=exc,
            extra={"billing_request_id": billing_request_id},
        )
        raise

    br_client_reference = str(getattr(billing_request, "client_reference", "") or "").strip()
    if not br_client_reference:
        _capture_gocardless_error(
            message="gocardless_missing_client_reference",
            level="warning",
            extra={"billing_request_id": billing_request_id},
        )
        return

    br_links = getattr(billing_request, "links", None)
    mandate_id = str(getattr(br_links, "mandate", "") or "").strip()
    customer_id = str(getattr(br_links, "customer", "") or "").strip()
    if not mandate_id:
        _capture_gocardless_error(
            message="gocardless_missing_mandate_id",
            level="warning",
            extra={"billing_request_id": billing_request_id, "empresa_id": br_client_reference},
        )
        return

    res_emp: Any = await db.execute(
        db.table("empresas")
        .select("id,email,nombre_comercial,nombre_legal")
        .eq("id", br_client_reference)
        .limit(1)
    )
    empresas = (res_emp.data or []) if hasattr(res_emp, "data") else []
    if not empresas:
        _capture_gocardless_error(
            message="gocardless_empresa_not_found_from_client_reference",
            level="warning",
            extra={
                "billing_request_id": billing_request_id,
                "client_reference_id": br_client_reference,
            },
        )
        return
    empresa = empresas[0]

    await db.execute(
        db.table("empresas")
        .update(
            {
                "gocardless_mandate_id": mandate_id,
                "gocardless_customer_id": customer_id or None,
            }
        )
        .eq("id", br_client_reference)
    )

    email = str(empresa.get("email") or "").strip()
    if email:
        company_name = (
            str(empresa.get("nombre_comercial") or empresa.get("nombre_legal") or "").strip()
            or "AB Logistics OS"
        )
        EmailService().send_welcome_enterprise(email, company_name)


@router.post("/gocardless", status_code=status.HTTP_204_NO_CONTENT)
async def gocardless_webhook_listener(
    request: Request,
    db: SupabaseAsync = Depends(deps.get_db_admin),
    webhook_signature: str | None = Header(default=None, alias="Webhook-Signature"),
) -> Response:
    body = await request.body()
    secret = get_secret_manager().get_gocardless_webhook_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GoCardless webhook no configurado en servidor.",
        )

    try:
        import gocardless_pro

        parsed = gocardless_pro.Webhook.parse(
            body.decode("utf-8"),
            str(webhook_signature or ""),
            secret,
        )
    except Exception as exc:
        _capture_gocardless_error(
            message="gocardless_webhook_signature_invalid",
            exc=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de webhook GoCardless inválida.",
        ) from exc

    events = getattr(parsed, "events", []) or []
    for raw_event in events:
        event = raw_event if isinstance(raw_event, dict) else {}
        ext_id = str(event.get("id") or "").strip()
        etype = _extract_event_type(event) or "unknown"
        if ext_id:
            first_delivery = await claim_webhook_event(
                db,
                provider="gocardless",
                external_event_id=ext_id,
                event_type=etype,
                payload=event,
                status="PENDING",
            )
            if not first_delivery:
                continue
        if etype == "billing_requests.fulfilled":
            try:
                await _process_billing_request_fulfilled(db=db, event=event)
            except Exception as exc:
                _log.exception("Error procesando billing_requests.fulfilled: %s", exc)
                _capture_gocardless_error(
                    message="gocardless_webhook_processing_failed",
                    exc=exc,
                    extra={"event_id": ext_id, "event_type": etype},
                )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
