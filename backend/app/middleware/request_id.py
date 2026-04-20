"""Correlación de peticiones HTTP (logs + Sentry + cabecera de respuesta)."""

from __future__ import annotations

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "x-request-id"


def _header_from_scope(scope: dict, name: bytes) -> str | None:
    for k, v in scope.get("headers") or []:
        if k.lower() == name.lower():
            try:
                return v.decode("utf-8").strip() or None
            except Exception:
                return None
    return None


def resolve_request_id_from_scope(scope: dict) -> str:
    raw = _header_from_scope(scope, REQUEST_ID_HEADER.encode("ascii"))
    if raw and len(raw) <= 128:
        return raw
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Propaga ``X-Request-ID`` (cliente o UUID), expone ``request.state.request_id``
    y la devuelve en la respuesta para trazabilidad end-to-end.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = resolve_request_id_from_scope(request.scope)
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response
