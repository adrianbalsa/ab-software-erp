"""
Middleware legado para healthchecks.

Se mantiene como no-op para no romper el orden de middlewares existente,
pero ya no cortocircuita ``GET /health`` porque ese endpoint ahora realiza
verificaciones reales de dependencias (Supabase + Redis).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class HealthCheckBypassMiddleware(BaseHTTPMiddleware):
    """No-op (compatibilidad)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        return await call_next(request)
