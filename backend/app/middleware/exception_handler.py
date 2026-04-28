from __future__ import annotations

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.services.notification_service import send_alert


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            asyncio.create_task(
                send_alert(
                    title="Unhandled exception",
                    message=str(exc) or "Unhandled backend exception",
                    level="CRITICAL",
                    context={
                        "path": str(request.url.path),
                        "method": request.method,
                        "error": str(exc),
                    },
                )
            )
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
