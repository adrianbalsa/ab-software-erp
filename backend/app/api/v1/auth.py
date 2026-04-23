"""Autenticación v1: recuperación de contraseña vía Resend (sin depender del SMTP de Supabase)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.security import create_password_reset_token, decode_password_reset_token
from app.db import supabase as supabase_db
from app.db.supabase import SupabaseAsync
from app.schemas.auth import ForgotPasswordIn, ForgotPasswordOut, ResetPasswordIn, ResetPasswordOut
from app.services.auth_service import AuthService
from app.services.email_service import (
    EmailService,
    _normalize_dest_email,
    send_email_background_task,
)

router = APIRouter()
_log = logging.getLogger(__name__)


async def get_db_admin() -> SupabaseAsync:
    """Service role (mismo criterio que ``deps.get_db_admin``) sin importar ``app.api.deps`` completo."""
    return await supabase_db.get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )


async def get_auth_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> AuthService:
    return AuthService(db)


@router.post("/forgot-password", response_model=ForgotPasswordOut)
async def forgot_password(
    payload: ForgotPasswordIn,
    background_tasks: BackgroundTasks,
    auth_service: AuthService = Depends(get_auth_service_admin),
) -> ForgotPasswordOut:
    """
    Genera JWT ``pwd_reset`` y envía enlace a ``/auth/reset-password`` por Resend.
    Respuesta genérica para no filtrar existencia de cuentas.
    """
    generic = ForgotPasswordOut()
    raw = (payload.email or "").strip()
    if not raw:
        return generic

    user = await auth_service.get_user(username=raw)
    if user is None or not (user.password_hash or "").strip():
        return generic

    dest = _normalize_dest_email(raw)
    if dest is None:
        dest = await auth_service.get_usuario_email_for_notifications(username=user.username)
    if dest is None:
        _log.warning("forgot-password: sin email de entrega (usuario prefix=%s)", user.username[:40])
        return generic

    try:
        token = create_password_reset_token(subject=user.username)
    except Exception as exc:
        _log.exception("forgot-password: no se pudo firmar token: %s", exc)
        return generic

    def _send_sync() -> bool:
        return EmailService().send_reset_password(dest, token)

    background_tasks.add_task(send_email_background_task, "password_reset_resend", _send_sync)
    return generic


@router.post("/reset-password", response_model=ResetPasswordOut)
async def reset_password(
    payload: ResetPasswordIn,
    auth_service: AuthService = Depends(get_auth_service_admin),
) -> ResetPasswordOut:
    """Aplica nueva contraseña tras validar JWT ``pwd_reset``."""
    sub = decode_password_reset_token(payload.token)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o caducado",
        )
    try:
        ok = await auth_service.set_password_for_username(username=sub, new_plain_password=payload.new_password)
    except ValueError as exc:
        if str(exc) == "password_too_short":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña debe tener al menos 8 caracteres",
            ) from exc
        raise
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo actualizar la contraseña",
        )
    return ResetPasswordOut()
