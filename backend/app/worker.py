from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any
import logging
from pathlib import Path

from arq.connections import RedisSettings
from arq.worker import Retry
from dotenv import load_dotenv
from redis import asyncio as redis_asyncio

from app.core.config import get_settings
from app.db.supabase import get_supabase
from app.services.audit_logs_service import AuditLogsService
from app.services.verifactu_sender import enviar_factura_aeat

_CURRENT_DIR = Path.cwd()
load_dotenv(dotenv_path=_CURRENT_DIR / ".env")
load_dotenv(dotenv_path=_CURRENT_DIR.parent / ".env")

_AEAT_EGRESS_LIMIT_PER_MINUTE = 30
_AEAT_EGRESS_BUCKET_KEY = "rl:egress:aeat:minute"
_log = logging.getLogger(__name__)


def redis_settings_from_env() -> RedisSettings:
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL es obligatoria para ejecutar el worker arq")
    return RedisSettings.from_dsn(url)


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
    await _acquire_aeat_egress_slot(ctx)
    result: dict[str, Any] | None = None
    action_result = "error"
    try:
        if _is_mock_mode_enabled():
            result = await _submit_to_aeat_mock_mode(factura_id=factura_id, empresa_id=empresa_id)
        else:
            result = await enviar_factura_aeat(str(factura_id))
        action_result = "success"
        return result
    except Exception:
        raise
    finally:
        try:
            db = await get_supabase(
                jwt_token=None,
                allow_service_role_bypass=True,
                log_service_bypass_warning=False,
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


class WorkerSettings:
    functions = [submit_to_aeat]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings_from_env()
    max_jobs = 30
    job_timeout = 300

