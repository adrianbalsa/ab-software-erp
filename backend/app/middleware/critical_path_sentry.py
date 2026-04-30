"""Etiquetas Sentry para rutas P1 (latencia / triage en Performance)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def classify_p1_critical_route(method: str, path: str) -> str | None:
    m = (method or "").upper()
    p = (path or "").rstrip("/") or "/"
    if m == "POST" and p.startswith("/api/v1/verifactu/submit-final/"):
        return "verifactu_submit_final"
    if m == "POST" and p == "/api/v1/advisor/ask":
        return "advisor_ask"
    if m == "GET" and p == "/health":
        return "health_readiness"
    if m == "GET" and p == "/api/v1/bi/financial-health":
        return "bi_financial_health"
    return None


class CriticalPathSentryTagsMiddleware(BaseHTTPMiddleware):
    """Añade ``p1_critical_route`` al scope Sentry en transacciones de endpoints críticos."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        label = classify_p1_critical_route(request.method, request.url.path)
        if label:
            try:
                import sentry_sdk

                sentry_sdk.get_isolation_scope().set_tag("p1_critical_route", label)
            except Exception:
                pass
        return await call_next(request)
