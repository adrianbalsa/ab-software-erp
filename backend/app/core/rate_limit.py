"""Claves y límites para rate limiting (tenant JWT, usuario o IP; auth por IP)."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import Response

from app.core.http_client_meta import get_client_ip
from app.core.security import decode_access_token_payload

_log = logging.getLogger(__name__)

# Endpoints sin límite (health, documentación, webhooks entrantes de terceros).
RATE_LIMIT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/health/deep",
        "/ready",
        "/openapi/swagger",
        "/openapi/redoc",
        "/openapi/openapi.json",
        "/favicon.ico",
    }
)
RATE_LIMIT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/webhooks/stripe",
    "/api/v1/routes",
    "/api/v1/chatbot",
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
    """
    Prioridad: ``empresa_id`` en JWT (multi-tenant) → ``sub``/usuario → IP.
    Rutas /auth/login|refresh usan middleware dedicado (no pasan por esta clave en SlowAPI).
    """
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            try:
                payload = decode_access_token_payload(token)
                eid = str(payload.get("empresa_id") or "").strip()
                if eid:
                    return f"e:{eid}"
                ident = str(
                    payload.get("usuario_id") or payload.get("sub") or ""
                ).strip()
                if ident:
                    return f"u:{ident}"
            except Exception:
                _log.debug("rate_limit: token no decodificable, fallback IP")

    ip = get_client_ip(request) or "unknown"
    return f"ip:{ip}"


def fiscal_aeat_submission_path(path: str, method: str) -> bool:
    """
    Envíos que pueden saturar AEAT: VeriFactu API, finalizar registro, reenvío SIF.
    """
    if method != "POST":
        return False
    p = path.rstrip("/")
    if p.startswith("/api/v1/verifactu"):
        return True
    if "/facturas/" in p and p.endswith("/finalizar"):
        return True
    if "/reenviar-aeat" in p:
        return True
    return False


def fiscal_rate_limit_key(request: Request) -> str:
    """Límite fiscal por tenant (``empresa_id`` en JWT) o fallback IP."""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            try:
                payload = decode_access_token_payload(token)
                eid = str(payload.get("empresa_id") or "").strip()
                if eid:
                    return f"vf:{eid}"
                uid = str(payload.get("sub") or payload.get("usuario_id") or "").strip()
                if uid:
                    return f"vf:u:{uid}"
            except Exception:
                pass
    ip = get_client_ip(request) or "unknown"
    return f"vf:ip:{ip}"


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    HTTP 429 con cuerpo estándar; conserva cabeceras Retry-After / X-RateLimit-* de SlowAPI.
    """
    retry_after_sec = 60
    try:
        vl = getattr(request.state, "view_rate_limit", None)
        lim = getattr(request.app.state, "limiter", None)
        if vl is not None and lim is not None:
            ws = lim.limiter.get_window_stats(vl[0], *vl[1])
            reset_ts = float(getattr(ws, "reset_time", getattr(ws, "reset", 0)))
            if reset_ts:
                retry_after_sec = max(1, int(reset_ts - time.time()))
    except Exception:
        pass
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "retry_after": f"{retry_after_sec} seconds",
        },
    )
    lim = getattr(request.app.state, "limiter", None)
    if lim is not None:
        return lim._inject_headers(response, getattr(request.state, "view_rate_limit", None))
    return response


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


# Tras ``rate_limit_key``: límite global SlowAPI 200/min por clave (empresa JWT > usuario > IP).
limiter = Limiter(key_func=rate_limit_key, default_limits=["200/minute"])
