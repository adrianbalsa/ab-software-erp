from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

from app.core.config import get_settings
from app.core.security import decode_access_token_payload
from app.db.supabase import get_supabase
from app.services.auth_service import AuthService

_log = logging.getLogger(__name__)

_PUBLIC_PREFIXES = (
    "/live",
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/",
)
_EXCLUDED_LOGIN_PATH_FRAGMENTS = ("/auth/login", "/login")

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
        method = (request.method or "").upper()
        is_excluded_login_path = any(fragment in path for fragment in _EXCLUDED_LOGIN_PATH_FRAGMENTS)
        if path != "/" and any(path.startswith(prefix.rstrip("/")) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)
        if is_excluded_login_path:
            return await call_next(request)

        token = _extract_access_token(request)
        try:
            if not token:
                raise PermissionError("missing access token")

            payload = decode_access_token_payload(token)
            subject = str(payload.get("sub") or "").strip()
            if not subject:
                raise PermissionError("missing subject in token payload")

            # Lookup de perfil con service role para evitar bloqueos por claims JWT
            # inválidos para roles Postgres (p. ej. role=admin) antes de fijar contexto.
            db = await get_supabase(
                jwt_token=None,
                allow_service_role_bypass=True,
                log_service_bypass_warning=False,
            )
            auth_service = AuthService(db)
            user = await auth_service.get_profile_by_subject(subject=subject)
            if user is None:
                raise PermissionError("subject not mapped to tenant profile")

            # Contexto de tenant y RBAC obligatorio para preservar aislamiento.
            await auth_service.ensure_empresa_context(empresa_id=user.empresa_id)
            await auth_service.ensure_rbac_context(user=user)
        except Exception as exc:
            _log.error(
                "TenantRBACContextMiddleware hard-fail %s %s: %s",
                method,
                path,
                exc,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Forbidden: tenant context validation failed "
                        "(subject must map to an active tenant profile)."
                    )
                },
            )

        return await call_next(request)
