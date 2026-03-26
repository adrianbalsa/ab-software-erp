"""
Webhooks salientes: firma HMAC-SHA256, envío HTTP asíncrono (BackgroundTasks) con reintentos.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from starlette.background import BackgroundTasks

from app.db.supabase import SupabaseAsync, get_supabase

_log = logging.getLogger(__name__)

EVENT_FACTURA_FINALIZADA = "factura.finalizada"
EVENT_PORTE_FACTURADO = "porte.facturado"

_MAX_ATTEMPTS = 3
_BACKOFF_SEC = (1.0, 2.0, 4.0)
_HTTP_TIMEOUT = 30.0


def _canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign_body(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _ab_signature_header(secret: str, body: bytes) -> str:
    """Cabecera X-AB-Signature: HMAC-SHA256 del cuerpo JSON (mismo formato sha256=...)."""
    return _sign_body(secret, body)


def dispatch_webhook_test(
    *,
    empresa_id: str,
    webhook_id: str,
    background_tasks: BackgroundTasks,
) -> None:
    """
    Envía un POST de prueba (payload ping) a la URL suscrita; firma con X-AB-Signature.
    Ejecuta en background (no bloquea la respuesta HTTP).
    """
    eid = str(empresa_id or "").strip()
    wid = str(webhook_id or "").strip()
    if not eid or not wid:
        return
    background_tasks.add_task(_run_single_webhook_test, eid, wid)


async def _run_single_webhook_test(empresa_id: str, webhook_id: str) -> None:
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    try:
        res: Any = await db.execute(
            db.table("webhooks")
            .select("id, empresa_id, event_type, target_url, secret_key, is_active")
            .eq("id", webhook_id)
            .eq("empresa_id", empresa_id)
            .eq("is_active", True)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            _log.warning("webhook test: no hay fila activa id=%s empresa=%s", webhook_id, empresa_id)
            return
        wh = rows[0]
        ping_payload: dict[str, Any] = {
            "ping": True,
            "test": True,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        await _deliver_b2b_webhook(
            db,
            wh,
            empresa_id=empresa_id,
            event_type="webhook.test",
            payload=ping_payload,
        )
    except Exception:
        _log.exception("webhook test: error id=%s empresa=%s", webhook_id, empresa_id)


def dispatch_webhook(
    *,
    empresa_id: str,
    event_type: str,
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Encola entrega de webhooks para la empresa y tipo de evento.
    No bloquea la respuesta HTTP (ejecuta tras enviar la respuesta al cliente).
    """
    eid = str(empresa_id or "").strip()
    if not eid:
        return
    background_tasks.add_task(
        _run_webhook_deliveries,
        eid,
        event_type,
        dict(payload),
    )


async def _run_webhook_deliveries(empresa_id: str, event_type: str, payload: dict[str, Any]) -> None:
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    try:
        endpoints = await _fetch_active_endpoints(db, empresa_id=empresa_id, event_type=event_type)
        for ep in endpoints:
            await _deliver_to_endpoint(db, ep, empresa_id=empresa_id, event_type=event_type, payload=payload)
        b2b = await _fetch_b2b_webhooks(db, empresa_id=empresa_id, event_type=event_type)
        for row in b2b:
            await _deliver_b2b_webhook(db, row, empresa_id=empresa_id, event_type=event_type, payload=payload)
    except Exception:
        _log.exception("webhook: error en _run_webhook_deliveries empresa=%s event=%s", empresa_id, event_type)


async def _fetch_active_endpoints(
    db: SupabaseAsync, *, empresa_id: str, event_type: str
) -> list[dict[str, Any]]:
    res: Any = await db.execute(
        db.table("webhook_endpoints")
        .select("id, empresa_id, url, secret, events, active")
        .eq("empresa_id", empresa_id)
        .eq("active", True)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    out: list[dict[str, Any]] = []
    for r in rows:
        evs = r.get("events") or []
        if isinstance(evs, list) and event_type in evs:
            out.append(r)
    return out


async def _fetch_b2b_webhooks(
    db: SupabaseAsync, *, empresa_id: str, event_type: str
) -> list[dict[str, Any]]:
    try:
        res: Any = await db.execute(
            db.table("webhooks")
            .select("id, empresa_id, event_type, target_url, secret_key, is_active")
            .eq("empresa_id", empresa_id)
            .eq("event_type", event_type)
            .eq("is_active", True)
        )
    except Exception:
        _log.debug("webhook: tabla public.webhooks no disponible o error de lectura", exc_info=True)
        return []
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    return rows


async def _deliver_b2b_webhook(
    db: SupabaseAsync,
    wh: dict[str, Any],
    *,
    empresa_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    wh_id = str(wh.get("id") or "").strip()
    url = str(wh.get("target_url") or "").strip()
    secret = str(wh.get("secret_key") or "")
    if not url or not secret:
        _log.warning("webhook B2B %s sin target_url o secret_key", wh_id)
        return

    body = _canonical_json(payload)
    signature = _ab_signature_header(secret, body)
    body_text = body.decode("utf-8")

    log_id = str(uuid.uuid4())
    log_row: dict[str, Any] = {
        "id": log_id,
        "empresa_id": empresa_id,
        "webhook_endpoint_id": None,
        "webhook_id": wh_id,
        "event_type": event_type,
        "payload": {"event": event_type, "empresa_id": empresa_id, "payload": payload, "delivery": "b2b"},
        "request_body": body_text,
        "attempts": 0,
        "failed_attempts": 0,
    }
    try:
        await db.execute(db.table("webhook_logs").insert(log_row))
    except Exception:
        _log.exception("webhook B2B: insert webhook_logs fallido webhook_id=%s", wh_id)
        return

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-AB-Signature": signature,
    }

    last_err: str | None = None
    last_status: int | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _patch_log(
            db,
            log_id=str(log_id),
            empresa_id=empresa_id,
            updates={
                "attempts": attempt,
                "failed_attempts": attempt - 1 if attempt > 1 else 0,
            },
        )
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
            last_status = int(resp.status_code)
            if 200 <= resp.status_code < 300:
                await _patch_log(
                    db,
                    log_id=str(log_id),
                    empresa_id=empresa_id,
                    updates={
                        "response_status": last_status,
                        "failed_attempts": 0,
                        "last_error": None,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                return
            if 400 <= resp.status_code < 500:
                last_err = f"HTTP {resp.status_code} (sin reintento 4xx)"
                break
            last_err = f"HTTP {resp.status_code}"
        except Exception as exc:
            last_err = str(exc)
            _log.info("webhook B2B intento %s/%s fallido: %s", attempt, _MAX_ATTEMPTS, last_err)

        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_SEC[attempt - 1] if attempt - 1 < len(_BACKOFF_SEC) else _BACKOFF_SEC[-1]
            await asyncio.sleep(delay)

    await _patch_log(
        db,
        log_id=str(log_id),
        empresa_id=empresa_id,
        updates={
            "response_status": last_status,
            "failed_attempts": _MAX_ATTEMPTS,
            "last_error": (last_err or "unknown")[:4000],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _deliver_to_endpoint(
    db: SupabaseAsync,
    ep: dict[str, Any],
    *,
    empresa_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    ep_id = str(ep.get("id") or "").strip()
    url = str(ep.get("url") or "").strip()
    secret = str(ep.get("secret") or "")
    if not url or not secret:
        _log.warning("webhook: endpoint %s sin url o secret", ep_id)
        return

    idem = str(uuid.uuid4())
    envelope: dict[str, Any] = {
        "event": event_type,
        "empresa_id": empresa_id,
        "idempotency_key": idem,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    body = _canonical_json(envelope)
    signature = _sign_body(secret, body)
    body_text = body.decode("utf-8")

    log_id = str(uuid.uuid4())
    log_row: dict[str, Any] = {
        "id": log_id,
        "empresa_id": empresa_id,
        "webhook_endpoint_id": ep_id,
        "event_type": event_type,
        "payload": envelope,
        "request_body": body_text,
        "attempts": 0,
        "failed_attempts": 0,
    }
    try:
        await db.execute(db.table("webhook_logs").insert(log_row))
    except Exception:
        _log.exception("webhook: insert webhook_logs fallido endpoint=%s", ep_id)
        return

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Webhook-Event": event_type,
        "X-Webhook-Signature": signature,
        "X-Webhook-Idempotency-Key": idem,
    }

    last_err: str | None = None
    last_status: int | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _patch_log(
            db,
            log_id=str(log_id),
            empresa_id=empresa_id,
            updates={
                "attempts": attempt,
                "failed_attempts": attempt - 1 if attempt > 1 else 0,
            },
        )
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
            last_status = int(resp.status_code)
            if 200 <= resp.status_code < 300:
                await _patch_log(
                    db,
                    log_id=str(log_id),
                    empresa_id=empresa_id,
                    updates={
                        "response_status": last_status,
                        "failed_attempts": 0,
                        "last_error": None,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                return
            if 400 <= resp.status_code < 500:
                last_err = f"HTTP {resp.status_code} (sin reintento 4xx)"
                break
            last_err = f"HTTP {resp.status_code}"
        except Exception as exc:
            last_err = str(exc)
            _log.info("webhook intento %s/%s fallido: %s", attempt, _MAX_ATTEMPTS, last_err)

        if attempt < _MAX_ATTEMPTS:
            delay = _BACKOFF_SEC[attempt - 1] if attempt - 1 < len(_BACKOFF_SEC) else _BACKOFF_SEC[-1]
            await asyncio.sleep(delay)

    await _patch_log(
        db,
        log_id=str(log_id),
        empresa_id=empresa_id,
        updates={
            "response_status": last_status,
            "failed_attempts": _MAX_ATTEMPTS,
            "last_error": (last_err or "unknown")[:4000],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _patch_log(
    db: SupabaseAsync,
    *,
    log_id: str,
    empresa_id: str,
    updates: dict[str, Any],
) -> None:
    await db.execute(
        db.table("webhook_logs").update(updates).eq("id", log_id).eq("empresa_id", empresa_id)
    )
