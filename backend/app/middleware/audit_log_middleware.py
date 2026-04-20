from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token_payload
from app.db.supabase import get_supabase
from app.services.auth_service import AuthService
from app.services.audit_logs_service import AuditLogsService
from app.services.security_secret_rotation_audit import ACTION_SECURITY_SECRET_ROTATION

_log = logging.getLogger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_METHOD_TO_ACTION = {
    "POST": "INSERT",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE",
    "GET": "UPDATE",
}
_SENSITIVE_GET_PATHS = {
    "/api/v1/finance/treasury-risk",
}


def _normalize_path(path: str | None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return "/"
    return raw if raw == "/" else raw.rstrip("/") or "/"


def _is_sensitive_get(method: str, path: str) -> bool:
    return method == "GET" and _normalize_path(path) in _SENSITIVE_GET_PATHS


def _extract_access_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token
    return None


def _safe_client_ip(request: Request) -> str | None:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",", 1)[0].strip() or None
    if request.client and request.client.host:
        return request.client.host
    return None


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Registra trazas de auditoría para peticiones mutantes y GET sensibles autenticadas.

    Requisitos de seguridad:
    - Escritura con JWT de usuario (no service role) para que `auth.uid()` sea válido.
    - Nunca rompe la petición principal si falla el insert de auditoría.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:  # type: ignore[override]
        method = (request.method or "").upper()
        path = _normalize_path(request.url.path)
        should_audit = method in _MUTATING_METHODS or _is_sensitive_get(method, path)

        token = _extract_access_token(request)
        response = await call_next(request)

        rotation_events = getattr(request.state, "security_secret_rotation_events", None) or []
        if token and rotation_events:
            for raw_ev in rotation_events:
                if not isinstance(raw_ev, dict):
                    continue
                asyncio.create_task(
                    self._log_secret_rotation_event(
                        request=request,
                        token=token,
                        event=raw_ev,
                        status_code=response.status_code,
                    )
                )

        if not should_audit:
            return response
        if not token:
            return response

        _log.info(
            "AuditLogMiddleware dispatch triggered: method=%s path=%s status=%s",
            method,
            path,
            response.status_code,
        )
        if _is_sensitive_get(method, path):
            await self._log_audit_request(
                request=request,
                token=token,
                status_code=response.status_code,
            )
        else:
            asyncio.create_task(
                self._log_audit_request(
                    request=request,
                    token=token,
                    status_code=response.status_code,
                )
            )
        return response

    async def _log_secret_rotation_event(
        self,
        *,
        request: Request,
        token: str,
        event: dict[str, Any],
        status_code: int,
    ) -> None:
        kind = str(event.get("secret_kind") or "").strip()
        if not kind:
            return
        success = bool(event.get("success"))
        detail = event.get("detail")
        method = (request.method or "").upper()
        path = _normalize_path(request.url.path)
        ip = _safe_client_ip(request)
        user_agent = request.headers.get("user-agent")
        try:
            payload = decode_access_token_payload(token)
            subject = str(payload.get("sub") or "").strip()
            if not subject:
                return

            db = await get_supabase(
                jwt_token=token,
                use_service_role_key=True,
            )
            auth_service = AuthService(db)
            audit_service = AuditLogsService(db)
            user = await auth_service.get_profile_by_subject(subject=subject)
            if user is None:
                return

            empresa_id = str(user.empresa_id)
            usuario_id = str(user.usuario_id) if user.usuario_id is not None else None
            changed_by_uuid: UUID | None = None
            if usuario_id:
                try:
                    changed_by_uuid = UUID(usuario_id)
                except ValueError:
                    changed_by_uuid = None

            safe_detail = str(detail or "").strip()
            if len(safe_detail) > 500:
                safe_detail = safe_detail[:500] + "…"

            new_value: dict[str, Any] = {
                "event": ACTION_SECURITY_SECRET_ROTATION,
                "secret_kind": kind,
                "success": success,
                "detail": safe_detail or None,
                "method": method,
                "endpoint": path,
                "ip": ip,
                "status_code": status_code,
                "usuario_id": usuario_id,
                "empresa_id": empresa_id,
                "user_agent": user_agent,
            }
            await audit_service.log_sensitive_action(
                empresa_id=empresa_id,
                table_name="security",
                record_id=kind,
                action=ACTION_SECURITY_SECRET_ROTATION,
                new_value=new_value,
                user_id=changed_by_uuid,
            )
        except Exception as exc:
            _log.warning(
                "AuditLogMiddleware SECURITY_SECRET_ROTATION error kind=%s: %s",
                kind,
                exc,
                exc_info=True,
            )

    async def _log_audit_request(self, *, request: Request, token: str, status_code: int) -> None:
        method = (request.method or "").upper()
        action = _METHOD_TO_ACTION.get(method, "UPDATE")
        path = _normalize_path(request.url.path)
        query = request.url.query or None
        ip = _safe_client_ip(request)
        user_agent = request.headers.get("user-agent")

        try:
            payload = decode_access_token_payload(token)
            subject = str(payload.get("sub") or "").strip()
            if not subject:
                return

            db = await get_supabase(
                jwt_token=token,
                use_service_role_key=True,
            )
            auth_service = AuthService(db)
            audit_service = AuditLogsService(db)
            user = await auth_service.get_profile_by_subject(subject=subject)
            if user is None:
                return

            empresa_id = str(user.empresa_id)
            usuario_id = str(user.usuario_id) if user.usuario_id is not None else None
            changed_by_uuid: UUID | None = None
            if usuario_id:
                try:
                    changed_by_uuid = UUID(usuario_id)
                except ValueError:
                    changed_by_uuid = None

            new_value: dict[str, Any] = {
                "method": method,
                "endpoint": path,
                "query": query,
                "ip": ip,
                "status_code": status_code,
                "usuario_id": usuario_id,
                "empresa_id": empresa_id,
                "user_agent": user_agent,
            }
            supplement = getattr(request.state, "audit_payload_supplement", None)
            if isinstance(supplement, dict) and supplement:
                new_value["extension_correo"] = supplement

            await audit_service.log_sensitive_action(
                empresa_id=empresa_id,
                table_name="api_requests",
                record_id=path,
                action=action,
                new_value=new_value,
                user_id=changed_by_uuid,
            )
        except Exception as exc:
            _log.warning(
                "AuditLogMiddleware error for %s %s: %s",
                method,
                path,
                exc,
                exc_info=True,
            )
