"""10/min por IP en /auth/login y /auth/refresh (SlowAPI no decora OAuth2 sin romper FastAPI)."""

from __future__ import annotations

import logging
import time

import anyio
from limits import parse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.http_client_meta import get_client_ip
from app.core.rate_limit import AUTH_RATE_LIMIT_PATHS, get_rate_limit_strategy

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
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": f"{ra} seconds",
                },
            )

        return await call_next(request)
