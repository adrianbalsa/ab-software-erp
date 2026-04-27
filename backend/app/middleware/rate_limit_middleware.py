"""Rate limiting especializado:
- auth login/refresh por IP
- buckets costosos (AI/Maps/OCR) por tenant/usuario/IP
"""

from __future__ import annotations

import logging
import time

import anyio
from limits import parse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.http_client_meta import get_client_ip
from app.core.rate_limit import (
    AUTH_RATE_LIMIT_PATHS,
    expensive_endpoint_bucket,
    get_rate_limit_strategy,
    is_rate_limit_exempt_path,
    rate_limit_key,
    rate_limit_response,
    resolve_rate_limit_identity,
)

_log = logging.getLogger(__name__)

_limit_auth = parse("10 per minute")


def _retry_after_seconds(strategy, limit_item, key: str) -> int:
    try:
        ws = strategy.get_window_stats(limit_item, key)
        rt = float(getattr(ws, "reset_time", 0))
        if rt:
            return max(1, int(rt - time.time()))
    except Exception:
        pass
    return 60


def _parse_limit_or_default(raw: str, fallback: str = "200 per minute"):
    try:
        return parse((raw or fallback).strip())
    except Exception:
        _log.warning("rate_limit: límite inválido %r; usando %s", raw, fallback)
        return parse(fallback)


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Límite HTTP global configurable por empresa.

    ``TENANT_RATE_LIMIT_DEFAULT`` cubre todos los tenants y
    ``TENANT_RATE_LIMIT_OVERRIDES`` permite límites por ``empresa_id``.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        if path in AUTH_RATE_LIMIT_PATHS or is_rate_limit_exempt_path(path):
            return await call_next(request)

        settings = get_settings()
        identity = resolve_rate_limit_identity(request)
        limit_raw = settings.TENANT_RATE_LIMIT_DEFAULT
        if identity.tenant_id:
            limit_raw = settings.TENANT_RATE_LIMIT_OVERRIDES.get(
                identity.tenant_id.lower(),
                limit_raw,
            )
        limit_item = _parse_limit_or_default(limit_raw)

        strategy = get_rate_limit_strategy()
        key = identity.key

        def _hit() -> bool:
            return strategy.hit(limit_item, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit tenant: error comprobando límite (dejamos pasar): %s", exc)
            return await call_next(request)

        if not ok:
            ra = _retry_after_seconds(strategy, limit_item, key)
            _log.warning(
                "rate_limit tenant exceeded key=%s scope=%s tenant_id=%s limit=%s",
                key,
                identity.scope,
                identity.tenant_id or "-",
                str(limit_item),
            )
            return rate_limit_response(
                request,
                retry_after_sec=ra,
                scope=identity.scope,
                tenant_id=identity.tenant_id,
                limit=str(limit_item),
            )

        return await call_next(request)


class AuthLoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Solo rutas de autenticación; el resto lo cubre SlowAPI (200/min por clave)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        if path not in AUTH_RATE_LIMIT_PATHS:
            return await call_next(request)

        strategy = get_rate_limit_strategy()
        ip = get_client_ip(request) or "unknown"
        key = f"rl:auth:ip:{ip}"

        def _hit() -> bool:
            return strategy.hit(_limit_auth, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit auth: error comprobando límite (dejamos pasar): %s", exc)
            return await call_next(request)

        if not ok:
            ra = _retry_after_seconds(strategy, _limit_auth, key)
            _log.warning(
                "rate_limit auth exceeded key=%s scope=ip limit=%s",
                key,
                str(_limit_auth),
            )
            return rate_limit_response(
                request,
                retry_after_sec=ra,
                scope="ip",
                limit=str(_limit_auth),
            )

        return await call_next(request)


class EndpointCostRateLimitMiddleware(BaseHTTPMiddleware):
    """Cuotas específicas para endpoints de coste alto (AI, Maps, OCR)."""

    @staticmethod
    def _limit_item_for_bucket(bucket: str):
        s = get_settings()
        if bucket == "ai":
            return _parse_limit_or_default(s.AI_RATE_LIMIT, "30 per minute")
        if bucket == "maps":
            return _parse_limit_or_default(s.MAPS_RATE_LIMIT, "120 per minute")
        return _parse_limit_or_default(s.OCR_RATE_LIMIT, "20 per minute")

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        bucket = expensive_endpoint_bucket(path, request.method)
        if bucket is None:
            return await call_next(request)

        strategy = get_rate_limit_strategy()
        base_key = rate_limit_key(request)
        key = f"{base_key}:bucket:{bucket}"
        limit_item = self._limit_item_for_bucket(bucket)

        def _hit() -> bool:
            return strategy.hit(limit_item, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit %s: error comprobando límite (dejamos pasar): %s", bucket, exc)
            return await call_next(request)

        if not ok:
            ra = _retry_after_seconds(strategy, limit_item, key)
            identity = resolve_rate_limit_identity(request)
            _log.warning(
                "rate_limit bucket exceeded key=%s bucket=%s scope=%s tenant_id=%s limit=%s",
                key,
                bucket,
                identity.scope,
                identity.tenant_id or "-",
                str(limit_item),
            )
            return rate_limit_response(
                request,
                retry_after_sec=ra,
                scope=identity.scope,
                tenant_id=identity.tenant_id,
                bucket=bucket,
                limit=str(limit_item),
            )

        return await call_next(request)
