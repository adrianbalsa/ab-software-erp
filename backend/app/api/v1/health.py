"""Healthcheck operativo para SRE (DB + Redis + disco).

Ruta: GET /api/v1/health

No es un "OK" estático: verifica conectividad y recursos para evitar que
logs/backups llenen disco o que Redis/DB estén caídos.
"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api import deps

router = APIRouter()


async def _check_postgres_via_supabase() -> tuple[bool, str | None]:
    """
    Verifica conectividad Postgres/DB a través de Supabase PostgREST.
    """
    try:
        db = await deps.get_db_admin()
        # Consulta trivial y barata: 1 fila.
        q = db.table("empresas").select("id").limit(1)
        res: Any = await db.execute(q)
        _rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


async def _check_redis_latency_ms(redis_url: str) -> tuple[bool, float | str | None]:
    try:
        r = redis_asyncio.from_url(redis_url, decode_responses=True)
        t0 = time.perf_counter()
        await r.ping()
        t1 = time.perf_counter()
        ms = (t1 - t0) * 1000.0
        # Cierra para evitar sockets huérfanos
        try:
            await r.aclose()
        except Exception:
            pass
        return True, ms
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _check_disk_free_bytes(path: str) -> tuple[bool, int]:
    usage = shutil.disk_usage(path)
    free = int(usage.free)
    min_free_mb = int(os.getenv("HEALTH_DISK_MIN_FREE_MB", "200"))
    min_free_bytes = min_free_mb * 1024 * 1024
    return free >= min_free_bytes, free


@router.get("/health", include_in_schema=False)
async def health_v1() -> JSONResponse:
    """
    - DB: ping a PostgREST (empresas).
    - Redis: PING y latencia.
    - Disco: espacio libre mínimo configurable.
    """

    checks: dict[str, Any] = {}

    db_ok, db_err = await _check_postgres_via_supabase()
    checks["postgres"] = {"ok": db_ok, "error": db_err}

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        checks["redis"] = {"ok": False, "error": "REDIS_URL no configurado"}
    else:
        redis_ok, redis_val = await _check_redis_latency_ms(redis_url)
        checks["redis"] = {"ok": redis_ok, "latency_ms": redis_val if redis_ok else None, "error": None if redis_ok else redis_val}

    disk_ok, free_bytes = _check_disk_free_bytes("/")
    checks["disk"] = {"ok": disk_ok, "free_bytes": free_bytes, "min_free_mb": int(os.getenv("HEALTH_DISK_MIN_FREE_MB", "200"))}

    ok = bool(db_ok and disk_ok and (checks["redis"]["ok"] is True))
    return JSONResponse(
        status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if ok else "degraded",
            "checks": checks,
        },
    )

