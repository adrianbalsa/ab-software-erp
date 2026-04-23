from __future__ import annotations

import json
import logging
import os
from typing import Any

_log = logging.getLogger(__name__)

_PREFIX = "scanner:vampire_radar:v1"


def ocr_cache_key(*, empresa_id: str, file_sha256: str) -> str:
    return f"{_PREFIX}:ocr:{empresa_id}:{file_sha256}"


async def _redis_client():
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return None
    try:
        import redis.asyncio as redis_asyncio

        return redis_asyncio.from_url(url, decode_responses=True)
    except Exception as exc:
        _log.warning("ai_document_cache: no se pudo crear cliente Redis: %s", exc)
        return None


async def cache_get_json(key: str) -> dict[str, Any] | None:
    r = await _redis_client()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        _log.warning("ai_document_cache get %s: %s", key, exc)
        return None
    finally:
        try:
            await r.aclose()
        except Exception:
            pass


async def cache_set_json(key: str, value: dict[str, Any], ttl_seconds: int = 604800) -> None:
    """TTL por defecto 7 días."""
    r = await _redis_client()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl_seconds)
    except Exception as exc:
        _log.warning("ai_document_cache set %s: %s", key, exc)
    finally:
        try:
            await r.aclose()
        except Exception:
            pass
