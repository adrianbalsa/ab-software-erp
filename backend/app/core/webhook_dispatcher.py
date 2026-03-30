"""
Envío de webhooks salientes con firma HMAC (cabecera X-ABLogistics-Signature).
Ejecutar el trabajo real vía BackgroundTasks para no bloquear la respuesta HTTP.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.db.supabase import SupabaseAsync, get_supabase
_log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SEC = (1.0, 2.0, 4.0)
_HTTP_TIMEOUT = 30.0

ABLOGISTICS_SIGNATURE_HEADER = "X-ABLogistics-Signature"

__all__ = [
    "ABLOGISTICS_SIGNATURE_HEADER",
    "build_ablogistics_signature_value",
    "canonical_json_str",
    "dispatch_webhook",
    "dispatch_endpoint_test",
    "run_dispatch_webhook_job",
    "run_single_endpoint_test_job",
]


def canonical_json_str(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def build_ablogistics_signature_value(*, secret_key: str, body_str: str) -> tuple[int, str]:
    """
    Devuelve (timestamp_unix, valor_cabecera) con formato t=timestamp,v1=hex_hmac_sha256(body).
    La firma es HMAC-SHA256 del cuerpo UTF-8 (JSON canónico) con el secreto del endpoint.
    """
    ts = int(time.time())
    digest = hmac.new(
        secret_key.encode("utf-8"),
        body_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return ts, f"t={ts},v1={digest}"


def _event_matches_subscription(event_types: object, event_type: str) -> bool:
    if not isinstance(event_types, list):
        return False
    evs = [str(x).strip() for x in event_types if str(x).strip()]
    if "*" in evs:
        return True
    return event_type in evs


async def _fetch_active_webhook_endpoints(
    db: SupabaseAsync, *, empresa_id: str, event_type: str
) -> list[dict[str, Any]]:
    res: Any = await db.execute(
        db.table("webhook_endpoints")
        .select("id, empresa_id, url, secret_key, event_types, is_active")
        .eq("empresa_id", empresa_id)
        .eq("is_active", True)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    return [r for r in rows if _event_matches_subscription(r.get("event_types"), event_type)]


async def _patch_webhook_log(
    db: SupabaseAsync,
    *,
    log_id: str,
    empresa_id: str,
    updates: dict[str, Any],
) -> None:
    await db.execute(
        db.table("webhook_logs").update(updates).eq("id", log_id).eq("empresa_id", empresa_id)
    )


async def _deliver_to_ablogistics_endpoint(
    db: SupabaseAsync,
    ep: dict[str, Any],
    *,
    empresa_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    ep_id = str(ep.get("id") or "").strip()
    url = str(ep.get("url") or "").strip()
    secret = str(ep.get("secret_key") or "")
    if not url or not secret:
        _log.warning("webhook endpoint %s sin url o secret_key", ep_id)
        return

    idem = str(uuid.uuid4())
    envelope: dict[str, Any] = {
        "event": event_type,
        "empresa_id": empresa_id,
        "idempotency_key": idem,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    body_str = canonical_json_str(envelope)
    _, sig_val = build_ablogistics_signature_value(secret_key=secret, body_str=body_str)

    log_id = str(uuid.uuid4())
    log_row: dict[str, Any] = {
        "id": log_id,
        "empresa_id": empresa_id,
        "webhook_endpoint_id": ep_id,
        "event_type": event_type,
        "payload": envelope,
        "request_body": body_str,
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
        ABLOGISTICS_SIGNATURE_HEADER: sig_val,
        "X-Webhook-Event": event_type,
        "X-Webhook-Idempotency-Key": idem,
    }

    last_err: str | None = None
    last_status: int | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _patch_webhook_log(
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
                resp = await client.post(url, content=body_str.encode("utf-8"), headers=headers)
            last_status = int(resp.status_code)
            if 200 <= resp.status_code < 300:
                await _patch_webhook_log(
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

    await _patch_webhook_log(
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


async def run_dispatch_webhook_job(empresa_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """
    Busca endpoints activos, firma y entrega (HTTP POST). Pensado para BackgroundTasks.
    """
    eid = str(empresa_id or "").strip()
    if not eid:
        return
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    try:
        endpoints = await _fetch_active_webhook_endpoints(db, empresa_id=eid, event_type=event_type)
        for ep in endpoints:
            await _deliver_to_ablogistics_endpoint(
                db, ep, empresa_id=eid, event_type=event_type, payload=dict(payload)
            )
    except Exception:
        _log.exception("webhook dispatcher: error empresa=%s event=%s", eid, event_type)


def dispatch_webhook(
    empresa_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    background_tasks: Any,
) -> None:
    """
    Encola la entrega a todos los ``webhook_endpoints`` activos suscritos al evento
    (o ``*``). Ejecutar vía FastAPI ``BackgroundTasks`` para no bloquear la respuesta.
    """
    eid = str(empresa_id or "").strip()
    if not eid:
        return
    background_tasks.add_task(run_dispatch_webhook_job, eid, event_type, dict(payload))


async def run_single_endpoint_test_job(empresa_id: str, endpoint_id: str) -> None:
    """POST de prueba firmado hacia la URL del endpoint (tabla webhook_endpoints)."""
    eid = str(empresa_id or "").strip()
    wid = str(endpoint_id or "").strip()
    if not eid or not wid:
        return
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    try:
        res: Any = await db.execute(
            db.table("webhook_endpoints")
            .select("id, empresa_id, url, secret_key, event_types, is_active")
            .eq("id", wid)
            .eq("empresa_id", eid)
            .eq("is_active", True)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            _log.warning("webhook endpoint test: no hay fila activa id=%s empresa=%s", wid, eid)
            return
        ping_payload: dict[str, Any] = {
            "ping": True,
            "test": True,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        await _deliver_to_ablogistics_endpoint(
            db,
            rows[0],
            empresa_id=eid,
            event_type="webhook.test",
            payload=ping_payload,
        )
    except Exception:
        _log.exception("webhook endpoint test: error id=%s empresa=%s", wid, eid)


def dispatch_endpoint_test(
    empresa_id: str,
    endpoint_id: str,
    *,
    background_tasks: Any,
) -> None:
    """Encola POST de prueba firmado hacia un ``webhook_endpoints`` concreto."""
    eid = str(empresa_id or "").strip()
    wid = str(endpoint_id or "").strip()
    if not eid or not wid:
        return
    background_tasks.add_task(run_single_endpoint_test_job, eid, wid)
