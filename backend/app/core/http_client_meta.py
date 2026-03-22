"""IP y cabeceras del cliente (proxies) [cite: 2026-03-22]."""

from __future__ import annotations

from starlette.requests import Request


def get_client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first[:45]
    if request.client and request.client.host:
        return str(request.client.host)[:45]
    return None
