"""Webhook receptor GoCardless (payments.confirmed)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from starlette.responses import Response

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.services.reconciliation_service import ReconciliationEngine
from app.services.webhook_idempotency import claim_webhook_event

router = APIRouter()
_log = logging.getLogger(__name__)


def _hmac_sha256_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _extract_event_type(event: dict[str, Any]) -> str:
    raw_t = event.get("event_type")
    if isinstance(raw_t, str) and raw_t.strip():
        return raw_t.strip().lower()
    resource = str(event.get("resource_type") or "").strip().lower()
    action = str(event.get("action") or "").strip().lower()
    if resource and action:
        return f"{resource}.{action}"
    return ""


def _extract_factura_id(event: dict[str, Any]) -> int | None:
    candidates: list[Any] = [
        (event.get("metadata") or {}).get("factura_id"),
        (event.get("links") or {}).get("factura_id"),
        (event.get("metadata") or {}).get("invoice_id"),
        (event.get("links") or {}).get("invoice_id"),
    ]
    for c in candidates:
        if c is None:
            continue
        try:
            return int(c)
        except (TypeError, ValueError):
            continue
    return None


def _extract_gocardless_customer_id(event: dict[str, Any]) -> str:
    metadata = event.get("metadata") or {}
    links = event.get("links") or {}
    metadata_links = metadata.get("links") if isinstance(metadata, dict) else {}
    candidates: list[Any] = [
        (metadata_links or {}).get("customer"),
        (metadata_links or {}).get("customer_id"),
        metadata.get("customer"),
        metadata.get("customer_id"),
        links.get("customer"),
        links.get("customer_id"),
        event.get("customer_id"),
        event.get("resource_id") if str(event.get("resource_type") or "").strip().lower() == "customers" else None,
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


async def _insert_audit_log_rpc(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    table_name: str,
    record_id: str,
    action: str,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
) -> None:
    params: dict[str, Any] = {
        "p_empresa_id": empresa_id,
        "p_table_name": table_name,
        "p_record_id": record_id,
        "p_action": action,
    }
    if old_data is not None:
        params["p_old_data"] = old_data
    if new_data is not None:
        params["p_new_data"] = new_data
    await db.rpc("audit_logs_insert_api_event", params)


async def _mark_factura_as_paid_and_audit(
    *,
    db: SupabaseAsync,
    event: dict[str, Any],
    body_digest: str,
) -> None:
    factura_id = _extract_factura_id(event)
    if factura_id is None:
        _log.info("gocardless webhook: evento sin factura_id; se omite")
        return

    res: Any = await db.execute(
        db.table("facturas")
        .select("id,empresa_id,estado_cobro,pago_id")
        .eq("id", factura_id)
        .limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        _log.info("gocardless webhook: factura id=%s no encontrada", factura_id)
        return

    row = rows[0]
    empresa_id = str(row.get("empresa_id") or "").strip()
    if not empresa_id:
        _log.warning("gocardless webhook: factura id=%s sin empresa_id", factura_id)
        return

    current_estado = str(row.get("estado_cobro") or "").strip().lower()
    payment_id = str((event.get("links") or {}).get("payment") or event.get("resource_id") or "").strip()

    if current_estado != "cobrada":
        await db.execute(
            db.table("facturas")
            .update(
                {
                    "estado_cobro": "cobrada",
                    "pago_id": payment_id or f"gocardless:{factura_id}",
                }
            )
            .eq("id", factura_id)
            .eq("empresa_id", empresa_id)
        )

    # Trazabilidad explícita (además del trigger de facturas).
    await _insert_audit_log_rpc(
        db=db,
        empresa_id=empresa_id,
        table_name="facturas",
        record_id=str(factura_id),
        action="UPDATE",
        old_data={"estado_cobro": row.get("estado_cobro"), "pago_id": row.get("pago_id")},
        new_data={
            "estado_cobro": "cobrada",
            "pago_id": payment_id or f"gocardless:{factura_id}",
            "source": "gocardless_webhook",
            "event_type": _extract_event_type(event),
            "event_id": str(event.get("id") or ""),
            "body_sha256": body_digest,
        },
    )


async def _mark_cliente_mandate_active_and_audit(
    *,
    db: SupabaseAsync,
    event: dict[str, Any],
    body_digest: str,
) -> None:
    customer_id = _extract_gocardless_customer_id(event)
    if not customer_id:
        _log.info("gocardless webhook: evento de mandato sin customer_id; se omite")
        return

    res_prof: Any = await db.execute(
        db.table("profiles")
        .select("cliente_id")
        .eq("gocardless_customer_id", customer_id)
        .limit(1)
    )
    prof_rows: list[dict[str, Any]] = (res_prof.data or []) if hasattr(res_prof, "data") else []
    if not prof_rows:
        _log.info("gocardless webhook: perfil no encontrado para customer_id=%s", customer_id)
        return

    cliente_id = str(prof_rows[0].get("cliente_id") or "").strip()
    if not cliente_id:
        _log.warning("gocardless webhook: perfil sin cliente_id para customer_id=%s", customer_id)
        return

    res_cliente: Any = await db.execute(
        db.table("clientes")
        .select("id,empresa_id,mandato_activo")
        .eq("id", cliente_id)
        .limit(1)
    )
    cli_rows: list[dict[str, Any]] = (res_cliente.data or []) if hasattr(res_cliente, "data") else []
    if not cli_rows:
        _log.info("gocardless webhook: cliente id=%s no encontrado", cliente_id)
        return

    cliente_row = cli_rows[0]
    empresa_id = str(cliente_row.get("empresa_id") or "").strip()
    if not empresa_id:
        _log.warning("gocardless webhook: cliente id=%s sin empresa_id", cliente_id)
        return

    old_mandato = bool(cliente_row.get("mandato_activo"))
    if not old_mandato:
        await db.execute(
            db.table("clientes")
            .update({"mandato_activo": True})
            .eq("id", cliente_id)
            .eq("empresa_id", empresa_id)
        )

    await _insert_audit_log_rpc(
        db=db,
        empresa_id=empresa_id,
        table_name="clientes",
        record_id=cliente_id,
        action="UPDATE",
        old_data={"mandato_activo": old_mandato},
        new_data={
            "mandato_activo": True,
            "evento": "mandate_activated",
            "source": "gocardless_webhook",
            "event_type": _extract_event_type(event),
            "event_id": str(event.get("id") or ""),
            "gocardless_customer_id": customer_id,
            "body_sha256": body_digest,
        },
    )


async def _process_gocardless_webhook(*, db: SupabaseAsync, payload: dict[str, Any], body: bytes) -> None:
    body_digest = hashlib.sha256(body).hexdigest()
    events = payload.get("events")
    if not isinstance(events, list):
        return
    engine = ReconciliationEngine(db)
    for raw in events:
        if not isinstance(raw, dict):
            continue
        event_type = _extract_event_type(raw)
        ext_id = str(raw.get("id") or "").strip()
        try:
            if ext_id:
                first_delivery = await claim_webhook_event(
                    db,
                    provider="gocardless",
                    external_event_id=ext_id,
                    event_type=event_type or "unknown",
                    payload=raw,
                    status="PENDING",
                )
                if not first_delivery:
                    continue
            else:
                await db.execute(
                    db.table("webhook_events").insert(
                        {
                            "provider": "gocardless",
                            "event_type": event_type or "unknown",
                            "payload": raw,
                            "status": "PENDING",
                            "error_log": None,
                        }
                    )
                )
        except Exception:
            _log.exception("gocardless webhook: no se pudo encolar webhook_events")
        try:
            if event_type == "payments.confirmed":
                await _mark_factura_as_paid_and_audit(db=db, event=raw, body_digest=body_digest)
                continue
            if event_type in {"mandates.created", "mandates.active"}:
                await _mark_cliente_mandate_active_and_audit(db=db, event=raw, body_digest=body_digest)
        except Exception:
            _log.exception("gocardless webhook: error procesando evento")
    try:
        await engine.poll_pending_queue(limit=min(len(events), 100))
    except Exception:
        _log.exception("gocardless webhook: error en polling de reconciliación")


@router.post(
    "/gocardless",
    status_code=204,
    summary="Webhook GoCardless (firma HMAC-SHA256)",
)
async def receive_gocardless_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: SupabaseAsync = Depends(deps.get_db_admin),
    webhook_signature: str | None = Header(default=None, alias="Webhook-Signature"),
) -> Response:
    from app.services.secret_manager_service import get_secret_manager

    secret = get_secret_manager().get_gocardless_webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="GoCardless webhook no configurado en servidor")

    body = await request.body()
    expected = _hmac_sha256_hex(secret=secret, body=body)
    provided = str(webhook_signature or "").strip().lower()
    if not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=498, detail="Invalid Token")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        # Respuesta rápida incluso con payload no parseable ya firmado.
        return Response(status_code=204)

    background_tasks.add_task(_process_gocardless_webhook, db=db, payload=payload, body=body)
    return Response(status_code=204)

