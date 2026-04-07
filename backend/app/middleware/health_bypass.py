"""
Fast-path GET /health antes de TrustedHostMiddleware (balanceadores con Host no listado).

El middleware debe registrarse **después** de ``TrustedHostMiddleware`` en ``main.py`` para quedar
más externo en la pila y ejecutarse primero en la petición entrante.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class HealthCheckBypassMiddleware(BaseHTTPMiddleware):
    """Responde 200 ``OK`` en ``GET /health`` sin delegar al resto de la pila."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.scope.get("type") == "http" and request.url.path == "/health":
            return Response(content="OK", media_type="text/plain", status_code=200)
        return await call_next(request)
