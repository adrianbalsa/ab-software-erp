"""Autenticación IAM v1: invitaciones, recuperación de contraseña y logout."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api import deps
from app.core.config import get_settings
from app.db import supabase as supabase_db
from app.db.supabase import SupabaseAsync
from app.schemas.auth import (
    AuthErrorOut,
    ForgotPasswordIn,
    ForgotPasswordOut,
    InviteUserIn,
    InviteUserOut,
    LogoutOut,
    ResetPasswordConfirmIn,
    ResetPasswordEmailIn,
    ResetPasswordEmailOut,
    ResetPasswordOut,
    ValidationErrorOut,
)
from app.schemas.user import UserOut
from app.services.refresh_token_service import RefreshTokenService

router = APIRouter()
_log = logging.getLogger(__name__)


async def get_db_admin() -> SupabaseAsync:
    """Service role (sin RLS) para operaciones Auth Admin y mantenimiento de perfiles."""
    return await supabase_db.get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )


async def get_db_anon() -> SupabaseAsync:
    """Cliente anónimo para flujos de recuperación basados en token OTP de Supabase."""
    return await supabase_db.get_supabase(jwt_token=None, allow_service_role_bypass=False)


def _extract_supabase_error_status(exc: Exception) -> int | None:
    for key in ("status_code", "status", "code"):
        raw = getattr(exc, key, None)
        if raw is None:
            continue
        try:
            code = int(raw)
        except (TypeError, ValueError):
            continue
        if 100 <= code <= 599:
            return code
    return None


def _is_supabase_bad_request(exc: Exception) -> bool:
    status_code = _extract_supabase_error_status(exc)
    if status_code is not None:
        return 400 <= status_code < 500
    text = str(exc or "").lower()
    markers = ("already", "invalid", "bad request", "unprocessable", "rate limit", "not found")
    return any(m in text for m in markers)


def _extract_invited_user_id(raw: Any) -> str | None:
    if isinstance(raw, dict):
        data = raw.get("user") if isinstance(raw.get("user"), dict) else raw.get("data")
        if isinstance(data, dict):
            uid = str(data.get("id") or "").strip()
            if uid:
                return uid
        uid = str(raw.get("id") or "").strip()
        if uid:
            return uid
    user_attr = getattr(raw, "user", None)
    if user_attr is not None:
        uid = str(getattr(user_attr, "id", "") or "").strip()
        if uid:
            return uid
    data_attr = getattr(raw, "data", None)
    if isinstance(data_attr, dict):
        uid = str(data_attr.get("id") or "").strip()
        if uid:
            return uid
    uid_attr = str(getattr(raw, "id", "") or "").strip()
    return uid_attr or None


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for key in (settings.ACCESS_TOKEN_COOKIE_NAME, settings.REFRESH_TOKEN_COOKIE_NAME):
        response.delete_cookie(key=key, path="/", domain=settings.COOKIE_DOMAIN)


_COMMON_AUTH_RESPONSES = {
    401: {"description": "No autenticado", "model": AuthErrorOut},
    403: {"description": "No autorizado", "model": AuthErrorOut},
    422: {"description": "Payload inválido", "model": ValidationErrorOut},
}


@router.post(
    "/invite",
    response_model=InviteUserOut,
    responses=_COMMON_AUTH_RESPONSES,
    summary="Invitar usuario (owner only)",
)
async def invite_user(
    payload: InviteUserIn,
    _: UserOut = Depends(deps.require_role("owner")),
    current_user: UserOut = Depends(deps.bind_write_context),
    db_admin: SupabaseAsync = Depends(get_db_admin),
) -> InviteUserOut:
    """
    Crea invitación en Supabase Auth y garantiza ``profiles.empresa_id`` heredado del owner invitador.
    """
    email = str(payload.email).strip().lower()
    requested_role = payload.role
    profile_role = "admin" if requested_role == "admin" else "traffic_manager"
    empresa_id = str(current_user.empresa_id)
    invite_metadata = {"empresa_id": empresa_id, "role": profile_role}
    try:
        invite_res = await db_admin.auth_admin_invite_user_by_email(
            email=email,
            options={"data": invite_metadata},
        )
    except Exception as exc:
        detail = str(exc).strip() or "Error al enviar invitación con Supabase Auth"
        if _is_supabase_bad_request(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc

    invited_user_id = _extract_invited_user_id(invite_res)
    if not invited_user_id:
        _log.warning("invite: Supabase no devolvió user.id para email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invitación enviada sin user.id; no se pudo garantizar herencia de empresa",
        )
    profile_payload = {
        "id": invited_user_id,
        "email": email,
        "username": email,
        "empresa_id": empresa_id,
        "role": profile_role,
        "rol": "admin" if requested_role == "admin" else "gestor",
    }
    try:
        await db_admin.execute(db_admin.table("profiles").upsert(profile_payload))
    except Exception as exc:
        _log.exception("invite: no se pudo upsert profiles para usuario invitado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invitación enviada, pero no se pudo garantizar empresa_id en profiles",
        ) from exc

    return InviteUserOut(
        invited_email=email,
        role=requested_role,
        empresa_id=empresa_id,
    )


@router.post(
    "/reset-password",
    response_model=ResetPasswordEmailOut,
    responses={
        401: _COMMON_AUTH_RESPONSES[401],
        403: _COMMON_AUTH_RESPONSES[403],
        422: _COMMON_AUTH_RESPONSES[422],
    },
    summary="Enviar email de recuperación (Supabase Auth)",
)
async def send_reset_password_email(
    payload: ResetPasswordEmailIn,
    db_anon: SupabaseAsync = Depends(get_db_anon),
) -> ResetPasswordEmailOut:
    redirect_to = payload.redirect_to or get_settings().PUBLIC_APP_URL
    try:
        options = {"redirect_to": redirect_to} if redirect_to else None
        await db_anon.auth_reset_password_for_email(email=str(payload.email).strip().lower(), options=options)
    except Exception as exc:
        detail = str(exc).strip() or "No se pudo iniciar recuperación de contraseña"
        if _is_supabase_bad_request(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
    return ResetPasswordEmailOut()


@router.post(
    "/reset-password/confirm",
    response_model=ResetPasswordOut,
    responses={
        401: _COMMON_AUTH_RESPONSES[401],
        403: _COMMON_AUTH_RESPONSES[403],
        422: _COMMON_AUTH_RESPONSES[422],
    },
    summary="Confirmar nuevo password con token de Supabase",
)
async def confirm_reset_password(
    payload: ResetPasswordConfirmIn,
    db_anon: SupabaseAsync = Depends(get_db_anon),
) -> ResetPasswordOut:
    try:
        await db_anon.auth_verify_otp({"type": "recovery", "token": payload.token})
        await db_anon.auth_update_user({"password": payload.new_password})
    except Exception as exc:
        detail = str(exc).strip() or "Token inválido o expirado"
        if _is_supabase_bad_request(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
    return ResetPasswordOut()


@router.post(
    "/logout",
    response_model=LogoutOut,
    responses={
        401: _COMMON_AUTH_RESPONSES[401],
        403: _COMMON_AUTH_RESPONSES[403],
        422: _COMMON_AUTH_RESPONSES[422],
    },
    summary="Cerrar sesión actual",
)
async def logout(
    request: Request,
    _: UserOut = Depends(deps.get_current_user),
    usuario_db_id: str | None = Depends(deps.get_usuario_db_id),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service),
) -> LogoutOut:
    settings = get_settings()
    raw_refresh = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    current_session_id = await refresh_service.resolve_current_session_id(raw_refresh=raw_refresh)
    if usuario_db_id and current_session_id:
        await refresh_service.revoke_session_for_user(session_id=current_session_id, user_id=usuario_db_id)
    response = JSONResponse(status_code=status.HTTP_200_OK, content=LogoutOut().model_dump())
    _clear_auth_cookies(response)
    return response


@router.post("/forgot-password", response_model=ForgotPasswordOut, include_in_schema=False)
async def forgot_password_legacy(
    payload: ForgotPasswordIn,
    db_anon: SupabaseAsync = Depends(get_db_anon),
) -> ForgotPasswordOut:
    try:
        await db_anon.auth_reset_password_for_email(email=str(payload.email).strip().lower(), options=None)
    except Exception:
        pass
    return ForgotPasswordOut()
