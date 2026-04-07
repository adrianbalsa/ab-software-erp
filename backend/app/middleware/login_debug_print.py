"""
Impresión stderr para depurar POST /auth/login antes del resto de la pila ASGI
(TrustedHost, lectura de body OAuth2, dependencias).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoginDebugPrintMiddleware(BaseHTTPMiddleware):
    """``print`` en POST ``/auth/login`` (y variante con slash). Debe ir **último** en ``add_middleware``."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if request.scope.get("type") == "http":
            path = request.url.path
            if request.method == "POST" and path.rstrip("/") == "/auth/login":
                host = request.client.host if request.client else "?"
                ct = request.headers.get("content-type") or ""
                cl = request.headers.get("content-length") or "?"
                print(
                    f"LOGIN ASGI EARLY: client_host={host!r} path={path!r} "
                    f"content-type={ct!r} content-length={cl!r}",
                    flush=True,
                )
        return await call_next(request)
