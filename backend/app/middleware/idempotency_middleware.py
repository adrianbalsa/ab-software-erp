from __future__ import annotations

import json
import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.rate_limit import resolve_rate_limit_identity

_log = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Scaffold para idempotencia HTTP por `Idempotency-Key`.

    Fase 2.3:
    - Intercepta requests mutantes (POST/PUT/PATCH/DELETE).
    - Reserva clave en Redis durante 24h.
    - Reutiliza respuesta cacheada para claves repetidas.
    """

    _redis_client: Any | None = None
    TTL_SECONDS = 24 * 60 * 60

    async def _redis(self) -> Any | None:
        if self._redis_client is not None:
            return self._redis_client
        url = (get_settings().REDIS_URL or "").strip()
        if not url:
            return None
        from redis import asyncio as redis_asyncio

        self._redis_client = redis_asyncio.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        return self._redis_client

    @staticmethod
    def _should_track(request: Request) -> bool:
        # GET/HEAD/OPTIONS no se cachean aquí: ya son idempotentes por definición.
        return request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}

    @staticmethod
    def _key(request: Request, idem_key: str) -> str:
        identity = resolve_rate_limit_identity(request)
        tenant_id = str(identity.tenant_id or "").strip()
        if not tenant_id:
            tenant_id = "anonymous"
        return f"idemp:{tenant_id}:{idem_key}"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._should_track(request):
            return await call_next(request)
        idem_key = str(request.headers.get("Idempotency-Key") or "").strip()
        if not idem_key:
            return await call_next(request)

        redis = await self._redis()
        if redis is None:
            _log.debug("idempotency: REDIS_URL no configurada, passthrough")
            return await call_next(request)

        key = self._key(request, idem_key)
        try:
            cached = await redis.get(key)
        except Exception as exc:
            _log.warning("idempotency: redis GET falló, fail-open activado: %s", exc)
            return await call_next(request)
        if cached:
            try:
                payload = json.loads(cached)
                body = payload.get("body", "")
                status_code = int(payload.get("status_code") or 200)
                headers = dict(payload.get("headers") or {})
                headers["X-Idempotency-Replayed"] = "true"
                return Response(content=body, status_code=status_code, headers=headers)
            except Exception:
                pass

        response = await call_next(request)
        if 200 <= int(response.status_code) < 300:
            try:
                body_bytes = b""
                async for chunk in response.body_iterator:
                    body_bytes += chunk
                stored = {
                    "status_code": int(response.status_code),
                    "headers": {"content-type": response.headers.get("content-type", "application/json")},
                    "body": body_bytes.decode("utf-8", errors="ignore"),
                }
                try:
                    await redis.set(key, json.dumps(stored, separators=(",", ":")), ex=self.TTL_SECONDS)
                except Exception as exc:
                    _log.warning("idempotency: redis SET falló, fail-open activado: %s", exc)
                return Response(
                    content=body_bytes,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            except Exception as exc:
                _log.debug("idempotency: no se pudo persistir respuesta: %s", exc)
        return response
