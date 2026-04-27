"""Claves y límites para rate limiting (tenant JWT, usuario o IP; auth por IP)."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from os import getenv
from typing import NamedTuple

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import Response

from app.core.http_client_meta import get_client_ip
from app.middleware.request_id import REQUEST_ID_HEADER, resolve_request_id_from_scope
from app.core.security import decode_access_token_payload

_log = logging.getLogger(__name__)
_RL_NS = "rl"


class RateLimitIdentity(NamedTuple):
    scope: str
    identifier: str
    key: str
    tenant_id: str | None


def _dev_mode_redis_rate_limit_bypass() -> bool:
    """Local-only: permitir rate limiting en memoria sin REDIS_URL."""
    return getenv("DEV_MODE", "").strip().lower() == "true"

# Endpoints sin límite (health, documentación, webhooks entrantes de terceros).
RATE_LIMIT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/live",
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


def resolve_rate_limit_identity(request: Request, *, namespace: str = "") -> RateLimitIdentity:
    """
    Prioridad: ``empresa_id`` en JWT (multi-tenant) → ``sub``/usuario → IP.
    Rutas /auth/login|refresh usan middleware dedicado (no pasan por esta clave en SlowAPI).
    """
    prefix = f"{_RL_NS}:{namespace}:" if namespace else f"{_RL_NS}:"
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            try:
                payload = decode_access_token_payload(token)
                eid = str(payload.get("empresa_id") or "").strip()
                if eid:
                    return RateLimitIdentity("tenant", eid, f"{prefix}tenant:{eid}", eid)
                ident = str(
                    payload.get("usuario_id") or payload.get("sub") or ""
                ).strip()
                if ident:
                    return RateLimitIdentity("user", ident, f"{prefix}user:{ident}", None)
            except Exception:
                _log.debug("rate_limit: token no decodificable, fallback IP")

    ip = get_client_ip(request) or "unknown"
    return RateLimitIdentity("ip", ip, f"{prefix}ip:{ip}", None)


def rate_limit_key(request: Request) -> str:
    """Clave estable para SlowAPI y buckets compartidos."""
    return resolve_rate_limit_identity(request).key


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
    return resolve_rate_limit_identity(request, namespace="fiscal").key


def expensive_endpoint_bucket(path: str, method: str) -> str | None:
    """
    Buckets de endpoints con coste elevado para cuotas específicas por tenant:
    - ai: llamadas LLM/chat
    - maps: geodistancia/optimización rutas
    - ocr: OCR tickets/adjuntos
    """
    m = (method or "").upper()
    p = (path or "").rstrip("/")

    if m == "POST" and p in {"/ai/chat", "/api/v1/advisor/ask", "/api/v1/chatbot/ask"}:
        return "ai"

    if (m == "GET" and p == "/maps/distance") or (
        m == "POST" and p == "/api/v1/routes/optimize-route"
    ):
        return "maps"

    if m == "POST" and (
        p.endswith("/gastos/ocr")
        or p.endswith("/gastos/ocr-hint")
        or p.endswith("/gastos/logistics-ticket")
    ):
        return "ocr"

    return None


def ensure_request_id(request: Request) -> str:
    """Devuelve/crea el request id aunque un rate limiter responda antes del middleware."""
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    rid = resolve_request_id_from_scope(request.scope)
    request.state.request_id = rid
    return rid


def rate_limit_response(
    request: Request,
    *,
    retry_after_sec: int,
    scope: str | None = None,
    tenant_id: str | None = None,
    bucket: str | None = None,
    limit: str | None = None,
) -> JSONResponse:
    """Respuesta 429 estándar, clara y trazable para todos los limitadores."""
    request_id = ensure_request_id(request)
    content: dict[str, object] = {
        "code": "rate_limit_exceeded",
        "error": "Rate limit exceeded",
        "message": "Demasiadas solicitudes. Reintenta cuando finalice la ventana de rate limit.",
        "retry_after": f"{max(1, retry_after_sec)} seconds",
        "request_id": request_id,
    }
    if scope:
        content["scope"] = scope
    if tenant_id:
        content["tenant_id"] = tenant_id
    if bucket:
        content["bucket"] = bucket
    if limit:
        content["limit"] = limit

    response = JSONResponse(status_code=429, content=content)
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers["Retry-After"] = str(max(1, retry_after_sec))
    return response


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
    identity = resolve_rate_limit_identity(request)
    response = rate_limit_response(
        request,
        retry_after_sec=retry_after_sec,
        scope=identity.scope,
        tenant_id=identity.tenant_id,
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
    """MovingWindow: Redis compartido en prod; memoria local si DEV_MODE sin REDIS_URL."""
    from limits.strategies import MovingWindowRateLimiter
    from limits.storage.memory import MemoryStorage
    from limits.storage.redis import RedisStorage

    from app.core.config import get_settings

    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        if _dev_mode_redis_rate_limit_bypass():
            _log.warning(
                "REDIS_URL no configurada: auth/fiscal rate limiting usa memoria local "
                "(DEV_MODE=true). Solo desarrollo; no apto multi-réplica."
            )
            return MovingWindowRateLimiter(MemoryStorage())
        _log.critical(
            "REDIS_URL no configurada: rate limiting no determinista entre réplicas; "
            "se aborta el arranque para proteger AEAT."
        )
        raise RuntimeError("Missing REDIS_URL for shared rate limiting")
    try:
        storage = RedisStorage(url)
    except Exception as exc:
        _log.critical("REDIS_URL inválida para rate limiting compartido: %s", exc)
        raise RuntimeError("Invalid REDIS_URL for shared rate limiting") from exc
    return MovingWindowRateLimiter(storage)


@lru_cache(maxsize=1)
def get_rate_limit_storage_uri() -> str:
    """URI de almacenamiento para SlowAPI (Redis compartido; opcional memory:// si DEV_MODE)."""
    from app.core.config import get_settings

    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        if _dev_mode_redis_rate_limit_bypass():
            _log.warning(
                "REDIS_URL no configurada: SlowAPI usa almacenamiento en memoria (DEV_MODE=true). "
                "Solo para desarrollo local; en producción configure REDIS_URL."
            )
            return "memory://"
        _log.critical(
            "REDIS_URL no configurada: SlowAPI no puede usar almacenamiento compartido; "
            "se aborta el arranque para evitar saturación AEAT."
        )
        raise RuntimeError("Missing REDIS_URL for SlowAPI storage")
    return url


async def warmup_rate_limit_backend() -> None:
    """
    Verifica conectividad a Redis y aborta arranque si falla (salvo bypass DEV_MODE sin URL).
    """
    from app.core.config import get_settings

    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        if _dev_mode_redis_rate_limit_bypass():
            _log.warning(
                "REDIS_URL no configurada: se omite comprobación Redis en warmup "
                "(DEV_MODE=true). Rate limiting en memoria solo para desarrollo local."
            )
            return
        _log.critical(
            "REDIS_URL no configurada: rate limiting distribuido no disponible; "
            "se aborta el arranque."
        )
        raise RuntimeError("Missing REDIS_URL for rate limiting backend")
    try:
        from redis import asyncio as redis_asyncio

        client = redis_asyncio.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await client.ping()
        finally:
            await client.aclose()
    except Exception as exc:
        _log.critical("rate_limit: no se pudo validar Redis en startup: %s", exc)
        raise RuntimeError("Redis unavailable for shared rate limiting") from exc


# SlowAPI conserva límites decorados (p. ej. endpoints públicos). El límite global por tenant
# lo aplica TenantRateLimitMiddleware para poder resolver overrides por empresa en runtime.
limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[],
    storage_uri=get_rate_limit_storage_uri(),
    strategy="moving-window",
)
