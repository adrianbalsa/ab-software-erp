"""
Registra en ``infra_health_logs`` peticiones que superan un umbral de duración (SRE).
No incluye query string (evita tokens en URL). Mensajes sanitizados vía ``health_service``.
"""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.health_service import log_slow_http_request


def _should_skip_slow_log(path: str) -> bool:
    if path in ("/ready", "/health"):
        return True
    if path.startswith("/health/"):
        return True
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    if path == "/openapi.json":
        return True
    return False


class SlowRequestLogMiddleware(BaseHTTPMiddleware):
    """Si la petición tarda > ``threshold_sec``, inserta fila en ``infra_health_logs``."""

    threshold_sec: float = 5.0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        if elapsed <= self.threshold_sec:
            return response

        path = request.url.path
        if _should_skip_slow_log(path):
            return response

        log_slow_http_request(
            latency_ms=round(elapsed * 1000, 3),
            path=path[:2000],
            method=request.method,
        )
        return response
