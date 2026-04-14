"""Endpoints de cumplimiento (RGPD) bajo `/api/v1/admin`."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.middleware.rbac_middleware import require_admin
from app.schemas.user import UserOut
from app.services.compliance import anonymize_user_data
from app.services.refresh_token_service import RefreshTokenService


router = APIRouter()


async def _target_empresa_id(db: SupabaseAsync, *, user_id: str) -> str | None:
    res: Any = await db.execute(
        db.table("usuarios").select("empresa_id").eq("id", user_id).limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        return None
    raw = rows[0].get("empresa_id")
    return str(raw).strip() if raw else None


@router.post("/compliance/anonymize/{user_id}")
async def post_anonymize_user(
    user_id: UUID,
    admin_user: UserOut = Depends(require_admin),
    usuario_db_id: str | None = Depends(deps.get_usuario_db_id),
    db: SupabaseAsync = Depends(deps.get_db_admin),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service_admin),
) -> dict:
    """
    Anonimiza PII del usuario (RGPD). Solo administradores de empresa; el usuario debe
    pertenecer a la misma empresa que el solicitante.
    """
    uid = str(user_id)
    empresa_target = await _target_empresa_id(db, user_id=uid)
    if empresa_target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if empresa_target != str(admin_user.empresa_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes anonimizar usuarios de otra empresa",
        )
    if usuario_db_id and uid == str(usuario_db_id).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes anonimizar tu propia sesión activa",
        )
    try:
        return await anonymize_user_data(
            db,
            user_id=user_id,
            refresh_service=refresh_service,
        )
    except ValueError as exc:
        if str(exc) == "Usuario no encontrado":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
