"""Claves y límites para rate limiting (usuario JWT o IP; auth por IP)."""

from __future__ import annotations

import logging
from functools import lru_cache

from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import Response

from app.core.http_client_meta import get_client_ip
from app.core.security import decode_access_token_payload

_log = logging.getLogger(__name__)

# Limiter global SlowAPI: IP del cliente; límite por defecto 100/min (middleware).
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Endpoints sin límite (health, documentación, webhooks entrantes de terceros).
RATE_LIMIT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/ready",
        "/openapi/swagger",
        "/openapi/redoc",
        "/openapi/openapi.json",
        "/favicon.ico",
    }
)
RATE_LIMIT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/payments/webhook",
    "/api/v1/stripe/webhook",
)

# Login / refresh: fuerza bruta por IP.
AUTH_RATE_LIMIT_PATHS: frozenset[str] = frozenset(
    {
        "/auth/login",
        "/auth/refresh",
    }
)


class SkipOptionsSlowAPIMiddleware(SlowAPIMiddleware):
    """
    Evita OPTIONS (CORS) y rutas /auth/login|/auth/refresh: esas usan AuthLoginRateLimitMiddleware
    (SlowAPI no puede decorar OAuth2PasswordRequestForm sin romper la introspección de FastAPI).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.scope.get("path") or ""
        if path in AUTH_RATE_LIMIT_PATHS or is_rate_limit_exempt_path(path):
            return await call_next(request)
        return await super().dispatch(request, call_next)


def rate_limit_key(request: Request) -> str:
    path = request.scope.get("path") or ""

    if path in AUTH_RATE_LIMIT_PATHS:
        ip = get_client_ip(request) or "unknown"
        return f"auth:{ip}"

    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            try:
                payload = decode_access_token_payload(token)
                ident = str(
                    payload.get("usuario_id") or payload.get("sub") or ""
                ).strip()
                if ident:
                    return f"u:{ident}"
            except Exception:
                _log.debug("rate_limit: token no decodificable, fallback IP")

    ip = get_client_ip(request) or "unknown"
    return f"ip:{ip}"


def is_rate_limit_exempt_path(path: str) -> bool:
    if path in RATE_LIMIT_EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in RATE_LIMIT_EXEMPT_PREFIXES)


@lru_cache(maxsize=1)
def get_rate_limit_strategy():
    """MovingWindow + Redis si hay REDIS_URL; si no, memoria (dev / single worker)."""
    from limits.storage import MemoryStorage
    from limits.strategies import MovingWindowRateLimiter

    from app.core.config import get_settings

    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if url:
        try:
            from limits.storage.redis import RedisStorage

            storage = RedisStorage(url)
        except Exception as exc:
            _log.warning("REDIS_URL inválida o Redis no disponible; rate limit en memoria: %s", exc)
            storage = MemoryStorage()
    else:
        storage = MemoryStorage()
    return MovingWindowRateLimiter(storage)
