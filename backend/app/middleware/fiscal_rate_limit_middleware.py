"""300/min por tenant en envíos fiscales AEAT (VeriFactu, finalizar, reenviar SIF)."""

from __future__ import annotations

import logging
import time

import anyio
from limits import parse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.rate_limit import fiscal_aeat_submission_path, fiscal_rate_limit_key, get_rate_limit_strategy

_log = logging.getLogger(__name__)

_limit_fiscal = parse("300 per minute")


def _retry_after_seconds(strategy, limit_item, key: str) -> int:
    try:
        ws = strategy.get_window_stats(limit_item, key)
        rt = float(getattr(ws, "reset_time", 0))
        if rt:
            return max(1, int(rt - time.time()))
    except Exception:
        pass
    return 60


class FiscalVerifactuRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Protege AEAT frente a ráfagas: clave por ``empresa_id`` (JWT) o IP.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.scope.get("path") or ""
        if not fiscal_aeat_submission_path(path, request.method):
            return await call_next(request)

        strategy = get_rate_limit_strategy()
        key = fiscal_rate_limit_key(request)

        def _hit() -> bool:
            return strategy.hit(_limit_fiscal, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit fiscal: error comprobando límite (dejamos pasar): %s", exc)
            return await call_next(request)

        if not ok:
            ra = _retry_after_seconds(strategy, _limit_fiscal, key)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": f"{ra} seconds",
                },
            )

        return await call_next(request)
