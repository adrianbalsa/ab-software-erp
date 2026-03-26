"""5/min por IP en /auth/login y /auth/refresh (SlowAPI no decora OAuth2 sin romper FastAPI)."""

from __future__ import annotations

import logging

import anyio
from limits import parse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.http_client_meta import get_client_ip
from app.core.rate_limit import AUTH_RATE_LIMIT_PATHS, get_rate_limit_strategy

_log = logging.getLogger(__name__)

_limit_auth = parse("5 per minute")


class AuthLoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Solo rutas de autenticación; el resto lo cubre SlowAPI (100/min por IP)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        if path not in AUTH_RATE_LIMIT_PATHS:
            return await call_next(request)

        strategy = get_rate_limit_strategy()
        ip = get_client_ip(request) or "unknown"
        key = f"auth:{ip}"

        def _hit() -> bool:
            return strategy.hit(_limit_auth, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit auth: error comprobando límite (dejamos pasar): %s", exc)
            return await call_next(request)

        if not ok:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas peticiones. Inténtelo más tarde."},
            )

        return await call_next(request)
