from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.db.supabase import SupabaseAsync
from app.schemas.finance import FinanceSummaryOut
from app.services.finance_service import FinanceService


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
    checks["pgbouncer"] = await check_pgbouncer_tcp()

    status = _overall_status(checks)
    return {
        "status": status,
        "checks": checks,
    }
