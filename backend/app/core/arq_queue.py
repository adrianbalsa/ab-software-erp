from __future__ import annotations

import asyncio
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis

from app.core.redis_config import billing_queue_name
from app.core.redis_config import redis_settings_from_env

_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


async def get_arq_redis_pool() -> ArqRedis:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            _pool = await create_pool(redis_settings_from_env(purpose="usar la cola arq"))
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
        _queue_name=billing_queue_name(),
    )
    if job is None:
        raise RuntimeError("No se pudo encolar el envío a AEAT")
    return str(job.job_id)


async def enqueue_mark_legacy_sha256_passwords(*, limit: int = 1000) -> str:
    redis = await get_arq_redis_pool()
    job = await redis.enqueue_job(
        "mark_legacy_sha256_passwords",
        int(limit),
        _queue_name=billing_queue_name(),
    )
    if job is None:
        raise RuntimeError("No se pudo encolar el marcado de passwords legacy SHA-256")
    return str(job.job_id)

