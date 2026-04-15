"""Raw ASGI middleware that bypasses all checks for GET /health."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send


class HealthCheckBypassMiddleware:
    """
    Bypass middleware for Railway and other load balancer healthcheck probes.
    It short-circuits `/health` before TrustedHost or tenant middlewares run.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/health":
            await self._send_ok(send)
            return
        await self.app(scope, receive, send)

    async def _send_ok(self, send: Send) -> None:
        payload = json.dumps({"status": "ok"}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": payload})
