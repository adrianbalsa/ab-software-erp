from __future__ import annotations

import asyncio
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


def _redis_settings_from_env() -> RedisSettings:
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL es obligatoria para usar la cola arq")
    return RedisSettings.from_dsn(url)


async def get_arq_redis_pool() -> ArqRedis:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            _pool = await create_pool(_redis_settings_from_env())
    return _pool


async def close_arq_redis_pool() -> None:
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.aclose(close_connection_pool=True)
            _pool = None


async def enqueue_submit_to_aeat(
    *,
    factura_id: int,
    empresa_id: str,
    usuario_id: str | None = None,
) -> str:
    redis = await get_arq_redis_pool()
    job = await redis.enqueue_job(
        "submit_to_aeat",
        int(factura_id),
        str(empresa_id),
        usuario_id,
    )
    if job is None:
        raise RuntimeError("No se pudo encolar el envío a AEAT")
    return str(job.job_id)

