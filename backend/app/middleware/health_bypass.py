"""Raw ASGI middleware: liveness barato en ``GET /live`` antes de TrustedHost / tenant."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.middleware.request_id import resolve_request_id_from_scope


class HealthCheckBypassMiddleware:
    """
    Liveness para balanceadores (Railway, etc.): ``GET /live`` responde 200 sin
    TrustedHost ni RBAC. La comprobación con dependencias sigue en ``GET /health``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/live":
            await self._send_ok(scope, send)
            return
        await self.app(scope, receive, send)

    async def _send_ok(self, scope: Scope, send: Send) -> None:
        rid = resolve_request_id_from_scope(scope)
        payload = json.dumps({"status": "ok", "request_id": rid}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode("ascii")),
            (b"x-request-id", rid.encode("utf-8")),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": payload})
