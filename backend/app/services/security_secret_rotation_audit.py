"""
Auditoría de rotación de secretos (evento ``SECURITY_SECRET_ROTATION``).

Nunca persiste ni registra valores de claves; solo metadatos (tipo, éxito, actor, mensaje seguro).
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request

from app.db.supabase import SupabaseAsync
from app.services.audit_logs_service import AuditLogsService, pseudonymize_audit_payload

_log = logging.getLogger(__name__)

ACTION_SECURITY_SECRET_ROTATION = "SECURITY_SECRET_ROTATION"


def queue_security_secret_rotation_audit(
    request: Request,
    *,
    secret_kind: str,
    success: bool,
    detail: str | None = None,
) -> None:
    """
    Encola metadatos para que ``AuditLogMiddleware`` persista ``SECURITY_SECRET_ROTATION``
    tras la petición (mismo canal que el resto de auditoría HTTP).
    """
    ev: dict[str, Any] = {
        "secret_kind": str(secret_kind).strip(),
        "success": bool(success),
        "detail": (detail or "").strip() or None,
    }
    bucket = getattr(request.state, "security_secret_rotation_events", None)
    if bucket is None:
        bucket = []
        request.state.security_secret_rotation_events = bucket
    bucket.append(ev)


async def log_security_secret_rotation(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    secret_kind: str,
    success: bool,
    actor: str | None = None,
    detail: str | None = None,
) -> None:
    """Inserta vía RPC el mismo canal que ``AuditLogsService`` (tabla audit_logs)."""
    safe_detail = (detail or "").strip()
    if len(safe_detail) > 500:
        safe_detail = safe_detail[:500] + "…"
    new_value: dict[str, Any] = {
        "event": ACTION_SECURITY_SECRET_ROTATION,
        "secret_kind": str(secret_kind).strip(),
        "success": bool(success),
        "actor": (actor or "").strip() or None,
        "detail": safe_detail or None,
    }
    _log.info(
        "SECURITY_SECRET_ROTATION empresa_id=%s kind=%s success=%s actor=%s",
        str(empresa_id)[:8] + "…",
        new_value["secret_kind"],
        success,
        new_value["actor"],
    )
    audit = AuditLogsService(db)
    await audit.log_sensitive_action(
        empresa_id=empresa_id,
        table_name="security",
        record_id=str(secret_kind).strip(),
        action=ACTION_SECURITY_SECRET_ROTATION,
        new_value=new_value,
    )


def log_security_secret_rotation_sync(
    *,
    supabase_client: Any,
    empresa_id: str,
    secret_kind: str,
    success: bool,
    actor: str | None = None,
    detail: str | None = None,
) -> None:
    """Variante síncrona para scripts CLI (cliente ``create_client`` de supabase-py)."""
    safe_detail = (detail or "").strip()
    if len(safe_detail) > 500:
        safe_detail = safe_detail[:500] + "…"
    new_value: dict[str, Any] = {
        "event": ACTION_SECURITY_SECRET_ROTATION,
        "secret_kind": str(secret_kind).strip(),
        "success": bool(success),
        "actor": (actor or "").strip() or None,
        "detail": safe_detail or None,
    }
    _log.info(
        "SECURITY_SECRET_ROTATION empresa_id=%s kind=%s success=%s",
        str(empresa_id)[:8] + "…",
        new_value["secret_kind"],
        success,
    )
    params = {
        "p_empresa_id": str(empresa_id).strip(),
        "p_table_name": "security",
        "p_record_id": str(secret_kind).strip(),
        "p_action": ACTION_SECURITY_SECRET_ROTATION,
        "p_new_data": pseudonymize_audit_payload(new_value),
    }
    if actor:
        params["p_changed_by"] = str(actor).strip()
    supabase_client.rpc("audit_logs_insert_api_event", params).execute()
