from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.core.redis_config import billing_queue_name
from app.db.supabase import SupabaseAsync
from app.schemas.finance import FinanceSummaryOut
from app.services.finance_service import FinanceService

_QUEUE_GROWTH_STATE_KEY_PREFIX = "health:redis_queue_growth"
_DEFAULT_QUEUE_GROWTH_ALERT_MINUTES = 15
_DEFAULT_QUEUE_GROWTH_MIN_DEPTH = 10


async def check_supabase_rest(settings_url: str, service_key: str) -> tuple[bool, str]:
    """
    Comprueba que la API REST de Supabase (PostgREST) responde.
    Usa la service key para evitar depender de tablas concretas.
    """
    base = settings_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{base}/rest/v1/",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
            )
            if r.status_code >= 500:
                return False, f"supabase_http_{r.status_code}"
            return True, "supabase_ok"
    except Exception as exc:
        return False, f"supabase_error:{exc!s}"


async def check_finance_service(db: SupabaseAsync) -> tuple[bool, str]:
    """Ejecuta ``financial_summary`` con un tenant sintético (debe no lanzar)."""
    try:
        svc = FinanceService(db)
        out: FinanceSummaryOut = await svc.financial_summary(
            empresa_id="00000000-0000-0000-0000-000000000000"
        )
        _ = out.ebitda
        return True, "finance_ok"
    except Exception as exc:
        return False, f"finance_error:{exc!s}"


def _check_dict(*, ok: bool, detail: str, skipped: bool = False) -> dict[str, Any]:
    return {"ok": ok, "detail": detail, "skipped": skipped}


def _env_positive_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _decode_redis_hash(raw: dict[Any, Any]) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for key, value in raw.items():
        k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        v = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        decoded[k] = v
    return decoded


def _queue_growth_alert_state(
    *,
    queue_depth: int,
    previous_depth: int | None,
    previous_growth_started_at: float | None,
    now_ts: float,
    threshold_minutes: int,
    min_depth: int,
) -> dict[str, Any]:
    is_growing = previous_depth is not None and queue_depth > previous_depth
    growth_active = queue_depth >= min_depth and is_growing
    growth_started_at = (
        previous_growth_started_at
        if growth_active and previous_growth_started_at is not None
        else now_ts if growth_active
        else None
    )
    growth_duration_seconds = (
        int(now_ts - growth_started_at) if growth_started_at is not None else 0
    )
    alert = growth_active and growth_duration_seconds >= threshold_minutes * 60

    return {
        "queue_growth_alert": alert,
        "queue_growth_detail": (
            "queue_depth_growing_sustained"
            if alert
            else "queue_depth_growing"
            if growth_active
            else "queue_depth_stable_or_below_threshold"
        ),
        "queue_growth_window_minutes": threshold_minutes,
        "queue_growth_min_depth": min_depth,
        "queue_growth_started_at": (
            int(growth_started_at) if growth_started_at is not None else None
        ),
        "queue_growth_duration_seconds": growth_duration_seconds,
    }


async def _queue_growth_alert_payload(
    client: Any,
    *,
    queue_name: str,
    queue_depth: int,
) -> dict[str, Any]:
    threshold_minutes = _env_positive_int(
        "REDIS_QUEUE_GROWTH_ALERT_MINUTES",
        _DEFAULT_QUEUE_GROWTH_ALERT_MINUTES,
    )
    min_depth = _env_positive_int(
        "REDIS_QUEUE_GROWTH_MIN_DEPTH",
        _DEFAULT_QUEUE_GROWTH_MIN_DEPTH,
    )
    state_key = f"{_QUEUE_GROWTH_STATE_KEY_PREFIX}:{queue_name}"
    now_ts = time.time()

    previous = _decode_redis_hash(await client.hgetall(state_key))
    try:
        previous_depth = int(previous["last_depth"]) if "last_depth" in previous else None
    except ValueError:
        previous_depth = None
    try:
        previous_growth_started_at = (
            float(previous["growth_started_at"]) if previous.get("growth_started_at") else None
        )
    except ValueError:
        previous_growth_started_at = None

    payload = _queue_growth_alert_state(
        queue_depth=queue_depth,
        previous_depth=previous_depth,
        previous_growth_started_at=previous_growth_started_at,
        now_ts=now_ts,
        threshold_minutes=threshold_minutes,
        min_depth=min_depth,
    )

    await client.hset(
        state_key,
        mapping={
            "last_depth": int(queue_depth),
            "growth_started_at": payload["queue_growth_started_at"] or "",
            "last_sample_at": int(now_ts),
        },
    )
    await client.expire(state_key, max(threshold_minutes * 60 * 4, 3600))
    return payload


async def check_postgresql_select_one() -> dict[str, Any]:
    """
    ``SELECT 1`` vía SQLAlchemy (Postgres directo o a través de PgBouncer en ``DATABASE_URL``).
    """
    from app.db.session import get_engine

    def _ping() -> str | None:
        eng = get_engine()
        if eng is None:
            return None
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"

    try:
        result = await asyncio.to_thread(_ping)
        if result is None:
            return _check_dict(ok=True, detail="DATABASE_URL not configured", skipped=True)
        return _check_dict(ok=True, detail="postgresql_select_1_ok", skipped=False)
    except Exception as exc:
        return _check_dict(ok=False, detail=f"postgresql_error:{exc!s}", skipped=False)


async def check_redis_ping() -> dict[str, Any]:
    """Ping a Redis si ``REDIS_URL`` está definida."""
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return _check_dict(ok=True, detail="REDIS_URL not configured", skipped=True)

    try:
        from redis import asyncio as redis_asyncio

        client = redis_asyncio.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return _check_dict(ok=True, detail="redis_ping_ok", skipped=False)
    except Exception as exc:
        return _check_dict(ok=False, detail=f"redis_error:{exc!s}", skipped=False)


async def check_redis_connectivity_for_compliance_report() -> dict[str, str]:
    """
    Misma fuente que la app: ``get_settings().REDIS_URL`` (resuelto desde env en arranque).
    Informe sin clave ``skipped``: si falta URL se lista ``missing_env:REDIS_URL``.
    Si conecta, añade rol y señales de persistencia desde ``INFO`` (AOF/RDB).
    """
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        return {
            "ok": "false",
            "detail": "missing_env:REDIS_URL (misma variable que app.core.config / redis_config / ARQ)",
            "redis_url_configured": "false",
        }

    try:
        from redis import asyncio as redis_asyncio

        client = redis_asyncio.from_url(
            url,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True,
        )
        try:
            pong = await client.ping()
            full = await client.info()
            role = str(full.get("role") or full.get("redis_mode") or "unknown")
            aof_on = int(full.get("aof_enabled", 0) or 0) == 1
            rdb_last = full.get("rdb_last_save_time")
            persist_bits: list[str] = []
            if aof_on:
                persist_bits.append("aof_enabled")
            if rdb_last:
                persist_bits.append("rdb_last_save_time_set")
            if not persist_bits:
                persist_bits.append("no_aof_no_rdb_snapshot_in_info_memory_only_risk")
            return {
                "ok": "true",
                "detail": "redis_connected",
                "redis_url_configured": "true",
                "pong": str(pong),
                "role": role,
                "persistence_summary": "+".join(persist_bits),
                "used_memory_human": str(full.get("used_memory_human") or ""),
            }
        finally:
            await client.aclose()
    except Exception as exc:
        return {
            "ok": "false",
            "detail": f"redis_error:{type(exc).__name__}",
            "redis_url_configured": "true",
        }


async def check_redis_queue_metrics() -> dict[str, Any]:
    """Metricas minimas de Redis/ARQ para observar bloqueos de cola."""
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return _check_dict(ok=True, detail="REDIS_URL not configured", skipped=True)

    try:
        from redis import asyncio as redis_asyncio

        queue_name = billing_queue_name()
        client = redis_asyncio.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            queue_depth = await client.zcard(queue_name)
            info = await client.info()
            growth_payload = await _queue_growth_alert_payload(
                client,
                queue_name=queue_name,
                queue_depth=int(queue_depth),
            )
        finally:
            await client.aclose()
        growth_alert = bool(growth_payload["queue_growth_alert"])
        return {
            "ok": not growth_alert,
            "detail": (
                "redis_queue_depth_growing_sustained"
                if growth_alert
                else "redis_queue_metrics_ok"
            ),
            "skipped": False,
            "queue_name": queue_name,
            "queue_depth": int(queue_depth),
            "connected_clients": int(info.get("connected_clients", 0) or 0),
            "blocked_clients": int(info.get("blocked_clients", 0) or 0),
            "used_memory": int(info.get("used_memory", 0) or 0),
            "rejected_connections": int(info.get("rejected_connections", 0) or 0),
            **growth_payload,
        }
    except Exception as exc:
        return _check_dict(ok=False, detail=f"redis_queue_metrics_error:{exc!s}", skipped=False)


async def check_geo_cache_economics() -> dict[str, Any]:
    """Métricas económicas de cache-aside para rutas externas."""
    try:
        from app.core.redis_cache import GeoCache
        from app.services.geo_service import _get_redis_client

        redis_client = await _get_redis_client()
        metrics = await GeoCache(redis_client).economics_metrics()
        return {
            "ok": True,
            "detail": "geo_cache_economics_ok",
            "skipped": redis_client is None,
            **metrics,
        }
    except Exception as exc:
        return _check_dict(ok=False, detail=f"geo_cache_economics_error:{exc!s}", skipped=False)


async def check_pgbouncer_tcp() -> dict[str, Any]:
    """
    Comprueba que el listener TCP de PgBouncer acepta conexiones.
    - Si ``PGBOUNCER_HEALTH_HOST`` está definido, usa host/puerto explícitos.
    - Si no, y ``DATABASE_URL`` apunta al puerto 6432, usa el host/puerto de la URL.
    - En caso contrario se omite (p. ej. solo Supabase HTTP).
    """
    explicit_host = (os.getenv("PGBOUNCER_HEALTH_HOST") or "").strip()
    explicit_port_raw = (os.getenv("PGBOUNCER_HEALTH_PORT") or "").strip()

    settings = get_settings()
    host: str | None = None
    port: int | None = None

    if explicit_host:
        host = explicit_host
        port = int(explicit_port_raw or "6432")
    elif settings.DATABASE_URL:
        parsed = urlparse(settings.DATABASE_URL)
        h = parsed.hostname
        p = parsed.port or 5432
        if p == 6432 and h:
            host, port = h, p

    if not host or not port:
        return _check_dict(
            ok=True,
            detail="PgBouncer TCP check skipped (set PGBOUNCER_HEALTH_HOST or use port 6432 in DATABASE_URL)",
            skipped=True,
        )

    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=3.0,
        )
        writer.close()
        await writer.wait_closed()
        return _check_dict(ok=True, detail=f"pgbouncer_tcp_ok:{host}:{port}", skipped=False)
    except Exception as exc:
        return _check_dict(ok=False, detail=f"pgbouncer_tcp_error:{exc!s}", skipped=False)


def _overall_status(checks: dict[str, dict[str, Any]]) -> str:
    def failed(c: dict[str, Any]) -> bool:
        if c.get("skipped"):
            return False
        return not c.get("ok", False)

    if any(failed(c) for c in checks.values()):
        return "degraded"
    return "healthy"


async def run_deep_health(*, supabase_url: str, service_key: str, db: SupabaseAsync) -> dict[str, Any]:
    """
    Salud profunda: Supabase REST, capa de negocio (finance), Postgres opcional,
    Redis opcional, listener PgBouncer opcional.
    """
    sup_ok, sup_detail = await check_supabase_rest(supabase_url, service_key)
    fin_ok, fin_detail = await check_finance_service(db)

    checks: dict[str, dict[str, Any]] = {
        "supabase": _check_dict(ok=sup_ok, detail=sup_detail, skipped=False),
        "finance_service": _check_dict(ok=fin_ok, detail=fin_detail, skipped=False),
    }

    checks["postgresql"] = await check_postgresql_select_one()
    checks["redis"] = await check_redis_ping()
    checks["redis_queue"] = await check_redis_queue_metrics()
    checks["geo_cache_economics"] = await check_geo_cache_economics()
    from app.services.geo_service import geocoding_cache_metrics

    checks["geocoding_cache"] = await geocoding_cache_metrics()
    checks["pgbouncer"] = await check_pgbouncer_tcp()
    from app.core.mtls_certificates import check_aeat_mtls_certificate_expiry

    checks["aeat_mtls_certificates"] = await check_aeat_mtls_certificate_expiry(db)

    status = _overall_status(checks)
    return {
        "status": status,
        "checks": checks,
    }
