from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.core.security import decode_access_token_payload
from app.db.supabase import get_supabase
from app.services.auth_service import AuthService

_log = logging.getLogger(__name__)

_PUBLIC_PREFIXES = (
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/",
)


def _extract_access_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    settings = get_settings()
    raw_cookie = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if raw_cookie and str(raw_cookie).strip():
        return str(raw_cookie).strip()
    return None


class TenantRBACContextMiddleware(BaseHTTPMiddleware):
    """
    Fija el contexto RLS de tenant/rol para peticiones autenticadas.
    """

    async def dispatch(self, request: Request, call_next: Any):  # type: ignore[override]
        path = request.url.path.rstrip("/") or "/"
        if path != "/" and any(path.startswith(prefix.rstrip("/")) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        token = _extract_access_token(request)
        if token:
            try:
                payload = decode_access_token_payload(token)
                subject = str(payload.get("sub") or "").strip()
                if subject:
                    db = await get_supabase(jwt_token=token)
                    auth_service = AuthService(db)
                    user = await auth_service.get_profile_by_subject(subject=subject)
                    if user is not None:
                        await auth_service.ensure_empresa_context(empresa_id=user.empresa_id)
                        await auth_service.ensure_rbac_context(user=user)
            except Exception as exc:
                # No romper la request: el control final sigue en dependencias auth/rbac.
                _log.debug("TenantRBACContextMiddleware omitido: %s", exc)

        return await call_next(request)
