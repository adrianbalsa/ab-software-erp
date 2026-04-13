"""RGPD: anonimización de datos personales (derecho al olvido) manteniendo integridad fiscal."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.security import hash_password_argon2id
from app.db.supabase import SupabaseAsync
from app.services.refresh_token_service import RefreshTokenService

logger = logging.getLogger(__name__)


def _anon_label(user_id: UUID) -> str:
    s = str(user_id).replace("-", "")[:12]
    return f"USUARIO_ANONIMO_{s}"


async def anonymize_user_data(
    db: SupabaseAsync,
    *,
    user_id: UUID,
    refresh_service: RefreshTokenService,
) -> dict[str, Any]:
    """
    Sustituye PII en ``usuarios`` / ``profiles``; revoca sesiones y vínculos OAuth.
    No elimina filas de ``facturas`` (legal hold); las facturas siguen asociadas al mismo tenant.
    """
    uid = str(user_id).strip()
    label = _anon_label(user_id)
    email_placeholder = f"anon_{label.lower()}@anon.invalid"
    random_hash = hash_password_argon2id(f"anon-{user_id}-revoked")

    res_u: Any = await db.execute(db.table("usuarios").select("id, empresa_id").eq("id", uid).limit(1))
    rows_u: list[dict[str, Any]] = (res_u.data or []) if hasattr(res_u, "data") else []
    if not rows_u:
        raise ValueError("Usuario no encontrado")

    payload_usuarios: dict[str, Any] = {
        "username": label,
        "email": email_placeholder,
        "nombre_completo": label,
        "password_hash": random_hash,
    }
    try:
        await db.execute(db.table("usuarios").update(payload_usuarios).eq("id", uid))
    except Exception as exc:
        logger.warning("anon usuarios: reintento sin columnas opcionales: %s", exc)
        minimal = {k: v for k, v in payload_usuarios.items() if k in ("username", "email", "password_hash")}
        await db.execute(db.table("usuarios").update(minimal).eq("id", uid))

    prof_payload: dict[str, Any] = {"username": label, "email": email_placeholder, "full_name": label}
    try:
        await db.execute(db.table("profiles").update(prof_payload).eq("id", uid))
    except Exception:
        try:
            await db.execute(
                db.table("profiles").update({"username": label, "email": email_placeholder}).eq("id", uid)
            )
        except Exception as exc:
            logger.warning("profiles anonymize id=%s: %s", uid[:8], exc)

    try:
        await db.execute(db.table("user_accounts").delete().eq("user_id", uid))
    except Exception as exc:
        logger.warning("user_accounts delete: %s", exc)

    try:
        await refresh_service.revoke_all_for_user(user_id=uid)
    except Exception as exc:
        logger.warning("anon revoke refresh tokens: %s", exc)

    return {"ok": True, "usuario_id": uid, "placeholder": label}
