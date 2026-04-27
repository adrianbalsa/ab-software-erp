from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any
import logging
from pathlib import Path

from arq import func
from arq.worker import Retry
from dotenv import load_dotenv
from redis import asyncio as redis_asyncio
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.redis_config import billing_queue_name
from app.core.redis_config import redis_settings_from_env
from app.db.supabase import get_supabase
from app.services.aeat_client_py import VeriFactuException
from app.services.audit_logs_service import AuditLogsService
from app.services.auth_service import AuthService
from app.services.verifactu_sender import enviar_factura_aeat

_CURRENT_DIR = Path.cwd()
load_dotenv(dotenv_path=_CURRENT_DIR / ".env")
load_dotenv(dotenv_path=_CURRENT_DIR.parent / ".env")

_AEAT_EGRESS_LIMIT_PER_MINUTE = 30
_AEAT_EGRESS_BUCKET_KEY = "rl:egress:aeat:minute"
_AEAT_JOB_MAX_TRIES = 6
_AEAT_JOB_BACKOFF_BASE_SECONDS = 10
_AEAT_JOB_BACKOFF_MAX_SECONDS = 300
_AEAT_RETRYABLE_RESULT_CODES = {"AEAT_TIMEOUT", "AEAT_CONNECTION", "REINTENTO_AGOTADO"}
_AEAT_NON_RETRYABLE_EXCEPTION_CODES = {"XSD_REQUEST", "SOAP_MALFORMED", "CERT", "CERT_READ", "XADES"}
_log = logging.getLogger(__name__)


def _job_try(ctx: dict[str, Any]) -> int:
    raw = ctx.get("job_try", 1)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def _retry_defer_seconds(ctx: dict[str, Any]) -> int:
    attempt = _job_try(ctx)
    return min(_AEAT_JOB_BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1)), _AEAT_JOB_BACKOFF_MAX_SECONDS)


def _can_retry_job(ctx: dict[str, Any]) -> bool:
    return _job_try(ctx) < _AEAT_JOB_MAX_TRIES


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, RedisError):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, VeriFactuException):
        code = str(getattr(exc, "code", "") or "")
        return code not in _AEAT_NON_RETRYABLE_EXCEPTION_CODES
    return False


def _is_retryable_result(result: dict[str, Any] | None) -> bool:
    if not result:
        return False
    estado = str(result.get("aeat_sif_estado") or result.get("estado") or "").strip()
    codigo = str(
        result.get("aeat_sif_codigo")
        or result.get("codigo_error")
        or result.get("codigo")
        or ""
    ).strip()
    return estado == "pendiente_envio" and codigo in _AEAT_RETRYABLE_RESULT_CODES


def _error_message(exc: Exception | None, result: dict[str, Any] | None) -> str | None:
    if exc is not None:
        return str(exc)[:2000]
    if not result:
        return None
    message = (
        result.get("aeat_sif_descripcion")
        or result.get("descripcion_error")
        or result.get("message")
        or result.get("detail")
        or repr(result)
    )
    return str(message)[:2000]


async def _record_verifactu_dead_job(
    db: Any,
    *,
    factura_id: int,
    empresa_id: str,
    ctx: dict[str, Any],
    result: dict[str, Any] | None,
    exc: Exception | None,
) -> None:
    """Persistir una única fila abierta para jobs VeriFactu agotados."""
    job_name = "submit_to_aeat"
    existing = await db.execute(
        db.table("verifactu_dead_jobs")
        .select("id")
        .eq("factura_id", int(factura_id))
        .eq("job_name", job_name)
        .eq("status", "open")
        .limit(1)
    )
    rows = (existing.data or []) if hasattr(existing, "data") else []
    if rows:
        return

    error_type = type(exc).__name__ if exc is not None else "RetryableResultExhausted"
    await db.execute(
        db.table("verifactu_dead_jobs").insert(
            {
                "empresa_id": str(empresa_id),
                "factura_id": int(factura_id),
                "job_name": job_name,
                "job_try": min(_job_try(ctx), _AEAT_JOB_MAX_TRIES),
                "max_tries": _AEAT_JOB_MAX_TRIES,
                "error_type": error_type,
                "error_message": _error_message(exc, result),
                "worker_result": result,
                "status": "open",
            }
        )
    )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL es obligatoria para ejecutar el worker arq")
    ctx["redis_client"] = redis_asyncio.from_url(url, socket_connect_timeout=2, socket_timeout=2)


async def shutdown(ctx: dict[str, Any]) -> None:
    client = ctx.get("redis_client")
    if client is not None:
        await client.aclose()


async def _acquire_aeat_egress_slot(ctx: dict[str, Any]) -> None:
    client = ctx["redis_client"]
    now = datetime.now(timezone.utc)
    bucket = f"{_AEAT_EGRESS_BUCKET_KEY}:{now.strftime('%Y%m%d%H%M')}"
    count = await client.incr(bucket)
    if count == 1:
        await client.expire(bucket, 120)
    if count > _AEAT_EGRESS_LIMIT_PER_MINUTE:
        raise Retry(defer=2)


def _is_mock_mode_enabled() -> bool:
    settings = get_settings()
    cert_pfx = (os.getenv("AEAT_CERT_PFX") or "").strip()
    return cert_pfx == "DUMMY_CERT_BASE64_PLACEHOLDER" or settings.ENVIRONMENT != "production"


async def _submit_to_aeat_mock_mode(*, factura_id: int, empresa_id: str) -> dict[str, Any]:
    await asyncio.sleep(2)
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_fingerprint = f"MOCK-SREI-{factura_id}-{int(datetime.now(timezone.utc).timestamp())}"
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    await db.execute(
        db.table("facturas")
        .update(
            {
                "fingerprint": mock_fingerprint,
                "aeat_sif_estado": "enviado_aeat",
                "aeat_sif_csv": mock_fingerprint,
                "aeat_sif_codigo": None,
                "aeat_sif_descripcion": "[MOCK] Simulación de envío AEAT completada",
                "aeat_sif_actualizado_en": now_iso,
            }
        )
        .eq("id", factura_id)
        .eq("empresa_id", empresa_id)
    )
    print(f"[MOCK] Factura {factura_id} processed successfully in simulation mode.")
    return {
        "ok": True,
        "mode": "mock",
        "factura_id": factura_id,
        "empresa_id": empresa_id,
        "fingerprint": mock_fingerprint,
        "aeat_sif_estado": "enviado_aeat",
        "processed_at": now_iso,
    }


async def submit_to_aeat(ctx: dict[str, Any], factura_id: int, empresa_id: str, usuario_id: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] | None = None
    action_result = "error"
    terminal_exc: Exception | None = None
    try:
        await _acquire_aeat_egress_slot(ctx)
        if _is_mock_mode_enabled():
            result = await _submit_to_aeat_mock_mode(factura_id=factura_id, empresa_id=empresa_id)
        else:
            result = await enviar_factura_aeat(str(factura_id))
        if _is_retryable_result(result):
            if _can_retry_job(ctx):
                defer = _retry_defer_seconds(ctx)
                action_result = "retry"
                _log.warning(
                    "submit_to_aeat retryable result factura_id=%s empresa_id=%s try=%s/%s defer=%ss code=%s",
                    factura_id,
                    empresa_id,
                    _job_try(ctx),
                    _AEAT_JOB_MAX_TRIES,
                    defer,
                    result.get("aeat_sif_codigo") or result.get("codigo_error") or result.get("codigo"),
                )
                raise Retry(defer=defer)
            action_result = "retry_exhausted"
            raise RuntimeError(f"AEAT retry exhausted for factura_id={factura_id}: {result!r}")
        action_result = "success"
        return result
    except Retry:
        if action_result == "error":
            action_result = "retry"
        raise
    except Exception as exc:
        terminal_exc = exc
        if _is_retryable_exception(exc) and _can_retry_job(ctx):
            defer = _retry_defer_seconds(ctx)
            action_result = "retry"
            _log.warning(
                "submit_to_aeat retryable exception factura_id=%s empresa_id=%s try=%s/%s defer=%ss exc=%s",
                factura_id,
                empresa_id,
                _job_try(ctx),
                _AEAT_JOB_MAX_TRIES,
                defer,
                exc,
            )
            raise Retry(defer=defer) from exc
        _log.exception(
            "submit_to_aeat failed factura_id=%s empresa_id=%s try=%s/%s",
            factura_id,
            empresa_id,
            _job_try(ctx),
            _AEAT_JOB_MAX_TRIES,
        )
        raise
    finally:
        try:
            db = await get_supabase(
                jwt_token=None,
                allow_service_role_bypass=True,
                log_service_bypass_warning=False,
            )
            if action_result == "retry_exhausted":
                try:
                    await _record_verifactu_dead_job(
                        db,
                        factura_id=factura_id,
                        empresa_id=empresa_id,
                        ctx=ctx,
                        result=result,
                        exc=terminal_exc,
                    )
                except Exception as dead_exc:
                    _log.warning(
                        "verifactu dead job log failed (factura_id=%s, empresa_id=%s): %s",
                        factura_id,
                        empresa_id,
                        dead_exc,
                    )
            audit_service = AuditLogsService(db)
            await audit_service.log_sensitive_action(
                empresa_id=empresa_id,
                table_name="facturas",
                record_id=str(factura_id),
                action="VERIFACTU_JOB_COMPLETED",
                new_value={
                    "factura_id": factura_id,
                    "empresa_id": empresa_id,
                    "action_result": action_result,
                    "job_try": _job_try(ctx),
                    "max_tries": _AEAT_JOB_MAX_TRIES,
                    "worker_result": result,
                    "mode": (result or {}).get("mode", "live"),
                },
                user_id=usuario_id,
            )
        except Exception as exc:
            _log.warning(
                "worker audit log failed (factura_id=%s, empresa_id=%s): %s",
                factura_id,
                empresa_id,
                exc,
            )


async def mark_legacy_sha256_passwords(ctx: dict[str, Any], limit: int = 1000) -> dict[str, Any]:
    """ARQ job: activa ``password_must_reset`` para cuentas con hashes SHA-256 legacy."""
    del ctx
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    marked = await AuthService(db).mark_legacy_sha256_passwords_for_reset(limit=limit)
    return {"ok": True, "marked": marked, "limit": max(1, min(int(limit or 1000), 5000))}


class WorkerSettings:
    functions = [
        func(submit_to_aeat, max_tries=_AEAT_JOB_MAX_TRIES),
        func(mark_legacy_sha256_passwords, max_tries=3),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings_from_env(purpose="ejecutar el worker arq")
    queue_name = billing_queue_name()
    max_jobs = 30
    job_timeout = 300
    keep_result = 86400
    health_check_interval = 60

