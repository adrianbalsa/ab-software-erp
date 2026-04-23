from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.i18n import normalize_lang
from app.core.rbac import normalize_rbac_role
from app.models.enums import normalize_user_role
from app.core.security import hash_password_argon2id, verify_password_against_stored

_NOTIFICATION_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserInDB, UserOut

logger = logging.getLogger(__name__)


def _auth_debug(msg: str, *args: object) -> None:
    """Logs de depuración login; activos solo si DEBUG=true (quitar o silenciar tras diagnosticar)."""
    if get_settings().DEBUG:
        logger.info("AUTH_DEBUG " + msg, *args)


def _uuid_or_none(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, TypeError):
        return None


class AuthService:
    """
    Async authentication service.

    Compatibility note:
    - SHA256 legacy en `usuarios.password_hash` sigue siendo válido hasta migración lazy a Argon2id.
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def attach_preferred_language(self, user: UserOut) -> UserOut:
        """
        ``usuarios.preferred_language`` prevalece sobre ``empresas.preferred_language``.
        """
        eid = str(user.empresa_id)
        emp_lang: str | None = None
        usr_lang: str | None = None
        try:
            re: Any = await self._db.execute(
                self._db.table("empresas").select("preferred_language").eq("id", eid).limit(1)
            )
            er = (re.data or []) if hasattr(re, "data") else []
            if er:
                emp_lang = str(er[0].get("preferred_language") or "").strip() or None
        except Exception:
            pass
        try:
            ru: Any = await self._db.execute(
                self._db.table("usuarios")
                .select("preferred_language")
                .eq("username", user.username)
                .limit(1)
            )
            ur = (ru.data or []) if hasattr(ru, "data") else []
            if ur:
                usr_lang = str(ur[0].get("preferred_language") or "").strip() or None
        except Exception:
            pass
        pref = normalize_lang(usr_lang) if usr_lang else normalize_lang(emp_lang) if emp_lang else "es"
        return user.model_copy(update={"preferred_language": pref})

    async def authenticate(self, *, username: str, password: str) -> UserOut | None:
        login_id = (username or "").strip()
        _auth_debug("authenticate start login_id=%s", login_id[:80])
        user = await self.get_user(username=username)
        if user is None:
            _auth_debug("authenticate no row in public.usuarios for login_id=%s", login_id[:80])
            return None
        has_hash = bool((user.password_hash or "").strip())
        _auth_debug(
            "authenticate user found id=%s username=%s email_match_used=yes password_hash_non_empty=%s",
            user.id,
            (user.username or "")[:64],
            has_hash,
        )
        if not has_hash:
            _auth_debug("authenticate abort: password_hash vacío en usuarios")
            return None
        ok, needs_argon2_upgrade = verify_password_against_stored(password, user.password_hash)
        if not ok:
            _auth_debug("authenticate password verification failed for usuario id=%s", user.id)
            return None
        canonical = user.username
        if needs_argon2_upgrade:
            await self._lazy_upgrade_password_hash(username=canonical, plain_password=password)
        profile = await self.get_profile_by_subject(subject=username)
        if profile is None and canonical != (username or "").strip():
            profile = await self.get_profile_by_subject(subject=canonical)
        if profile is not None and profile.empresa_id:
            _auth_debug(
                "authenticate using profiles rbac_role=%s empresa_id=%s",
                profile.rbac_role,
                profile.empresa_id,
            )
            return await self.attach_preferred_language(profile)
        if not user.empresa_id:
            _auth_debug(
                "authenticate abort: sin profile con empresa y usuarios.empresa_id vacío (usuario=%s)",
                (user.username or "")[:64],
            )
            return None
        rbac = normalize_rbac_role(None, legacy_rol=user.rol)
        _auth_debug("authenticate fallback UserOut from usuarios only rbac_role=%s", rbac)
        base = UserOut(
            username=user.username,
            empresa_id=user.empresa_id,
            role=normalize_user_role(None, legacy_role=user.rol),
            rol=user.rol,
            rbac_role=rbac,
            cliente_id=None,
            usuario_id=None,
        )
        return await self.attach_preferred_language(base)

    async def _lazy_upgrade_password_hash(self, *, username: str, plain_password: str) -> None:
        """Tras login válido con SHA256, reescribe `password_hash` con Argon2id. [cite: 2026-03-22]"""
        try:
            new_hash = hash_password_argon2id(plain_password)
            await self._db.execute(
                self._db.table("usuarios")
                .update({"password_hash": new_hash})
                .eq("username", username)
            )
            logger.info("password_hash migrado a Argon2id (usuario=%s)", username[:48])
        except Exception as exc:
            logger.warning("Migración lazy Argon2id omitida para %s: %s", username[:48], exc)

    async def get_user_out_for_refresh(self, *, usuario_id: str) -> UserOut | None:
        """
        Resuelve ``UserOut`` tras rotación de refresh (por ``usuarios.id``).
        Prioriza ``profiles`` si existe fila alineada con el username del usuario.
        """
        uid = str(usuario_id or "").strip()
        if not uid:
            return None
        try:
            q = self._db.table("usuarios").select("*").eq("id", uid).limit(1)
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            logger.warning("get_user_out_for_refresh: lectura usuarios falló: %s", exc)
            return None
        if not rows:
            return None
        row = rows[0]
        username = str(row.get("username") or "").strip()
        if not username:
            return None
        empresa_id = str(row.get("empresa_id") or "").strip()
        rol = str(row.get("rol") or "user").strip() or "user"
        profile = await self.get_profile_by_subject(subject=username)
        if profile is not None and profile.empresa_id:
            return profile
        if not empresa_id:
            return None
        base = UserOut(
            username=username,
            empresa_id=UUID(empresa_id),
            role=normalize_user_role(None, legacy_role=rol),
            rol=rol,
            rbac_role=normalize_rbac_role(None, legacy_rol=rol),
            cliente_id=None,
            usuario_id=None,
        )
        return await self.attach_preferred_language(base)

    async def get_usuario_by_email(self, *, email: str) -> UserInDB | None:
        """
        Resuelve ``usuarios`` por email (insensible a mayúsculas) o por ``username`` igual al email.
        Usado por OAuth Google: solo usuarios ya dados de alta pueden vincularse.
        """
        em = (email or "").strip().lower()
        if not em:
            return None
        try:
            q = self._db.table("usuarios").select("*").ilike("email", em).limit(1)
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                q2 = self._db.table("usuarios").select("*").eq("username", em).limit(1)
                res2: Any = await self._db.execute(q2)
                rows = (res2.data or []) if hasattr(res2, "data") else []
        except Exception as exc:
            logger.warning("get_usuario_by_email: lectura usuarios falló: %s", exc)
            return None
        if not rows:
            return None
        row = rows[0]
        try:
            raw_id = row.get("id")
            uid: UUID | None = None
            if raw_id is not None and str(raw_id).strip():
                uid = UUID(str(raw_id).strip())
            return UserInDB(
                id=uid,
                username=str(row.get("username") or ""),
                empresa_id=UUID(str(row.get("empresa_id") or "").strip()),
                rol=str(row.get("rol") or "user"),
                password_hash=str(row.get("password_hash") or ""),
            )
        except Exception:
            return None

    async def link_google_account(self, *, user_id: UUID, google_sub: str) -> None:
        """
        Inserta o confirma fila en ``user_accounts`` (provider=google, provider_subject=sub).
        Si ``sub`` ya está vinculado a otro ``usuarios.id``, lanza ``ValueError(google_already_linked)``.
        """
        sid = str(google_sub or "").strip()
        if not sid:
            raise ValueError("invalid_google_sub")
        q = (
            self._db.table("user_accounts")
            .select("user_id")
            .eq("provider", "google")
            .eq("provider_subject", sid)
            .limit(1)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        uid_s = str(user_id)
        if rows:
            existing = str(rows[0].get("user_id") or "").strip()
            if existing and existing != uid_s:
                raise ValueError("google_already_linked")
            return
        await self._db.execute(
            self._db.table("user_accounts").insert(
                {
                    "user_id": uid_s,
                    "provider": "google",
                    "provider_subject": sid,
                }
            )
        )

    async def get_user(self, *, username: str) -> UserInDB | None:
        """
        Resuelve ``usuarios`` (no ``profiles``): primero ``username`` exacto, luego ``email``
        exacto (tal cual y en minúsculas), y por último ``ilike`` en email (compatibilidad).
        """
        val = (username or "").strip()
        if not val:
            return None
        rows: list[dict[str, Any]] = []
        try:
            q = self._db.table("usuarios").select("*").eq("username", val).limit(1)
            res: Any = await self._db.execute(q)
            rows = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                qe = self._db.table("usuarios").select("*").eq("email", val).limit(1)
                res_e: Any = await self._db.execute(qe)
                rows = (res_e.data or []) if hasattr(res_e, "data") else []
            if not rows:
                qe2 = self._db.table("usuarios").select("*").eq("email", val.lower()).limit(1)
                res_e2: Any = await self._db.execute(qe2)
                rows = (res_e2.data or []) if hasattr(res_e2, "data") else []
            if not rows:
                q2 = self._db.table("usuarios").select("*").ilike("email", val.lower()).limit(1)
                res2: Any = await self._db.execute(q2)
                rows = (res2.data or []) if hasattr(res2, "data") else []
        except Exception as exc:
            logger.warning("get_user: lectura usuarios falló: %s", exc)
            return None
        if not rows:
            return None
        row = rows[0]
        try:
            raw_id = row.get("id")
            uid: UUID | None = None
            if raw_id is not None and str(raw_id).strip():
                uid = UUID(str(raw_id).strip())
            return UserInDB(
                id=uid,
                username=str(row.get("username") or ""),
                empresa_id=UUID(str(row.get("empresa_id") or "").strip()),
                rol=str(row.get("rol") or "user"),
                password_hash=str(row.get("password_hash") or ""),
            )
        except Exception:
            return None

    async def _fetch_profile_row(self, column: str, value: str) -> dict[str, Any] | None:
        """
        Lectura de `profiles` aislada: errores de esquema/red no deben tumbar toda la app
        ni confundirse con 'sesión inválida' por fallos en otras tablas (p. ej. empresas).
        """
        try:
            query = self._db.table("profiles").select("*").eq(column, value).limit(1)
            res: Any = await self._db.execute(query)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            return rows[0] if rows else None
        except Exception as exc:
            logger.warning(
                "profiles lookup omitido (%s=%s…): %s",
                column,
                str(value)[:32],
                exc,
            )
            return None

    def _profile_row_to_user_out(self, row: dict[str, Any], *, subject: str) -> UserOut | None:
        raw_empresa = row.get("empresa_id")
        empresa_s = str(raw_empresa).strip() if raw_empresa is not None else ""
        if not empresa_s:
            return None
        try:
            empresa_uuid = UUID(empresa_s)
        except ValueError:
            return None
        username = str(row.get("username") or row.get("email") or subject).strip()
        if not username:
            username = subject
        legacy_rol_raw = row.get("rol")
        rol = str(legacy_rol_raw).strip() if legacy_rol_raw is not None else "user"
        if not rol:
            rol = "user"
        rbac_role = normalize_rbac_role(row.get("role"), legacy_rol=rol)
        user_role = normalize_user_role(row.get("role"), legacy_role=rol)
        raw_vid = row.get("assigned_vehiculo_id")
        assigned_vid: UUID | None = None
        if raw_vid is not None and str(raw_vid).strip():
            try:
                assigned_vid = UUID(str(raw_vid).strip())
            except ValueError:
                assigned_vid = None
        raw_uid = row.get("id")
        usuario_uuid: UUID | None = None
        if raw_uid is not None and str(raw_uid).strip():
            try:
                usuario_uuid = UUID(str(raw_uid).strip())
            except ValueError:
                usuario_uuid = None
        raw_cid = row.get("cliente_id")
        cliente_uuid: UUID | None = None
        if raw_cid is not None and str(raw_cid).strip():
            try:
                cliente_uuid = UUID(str(raw_cid).strip())
            except ValueError:
                cliente_uuid = None
        return UserOut(
            username=username,
            empresa_id=empresa_uuid,
            role=user_role,
            rol=rol,
            rbac_role=rbac_role,
            cliente_id=cliente_uuid,
            assigned_vehiculo_id=assigned_vid,
            usuario_id=usuario_uuid,
        )

    async def get_profile_by_subject(self, *, subject: str) -> UserOut | None:
        """
        Resuelve empresa (y rol) desde `profiles` usando el claim `sub` del JWT.

        Se prueba en orden: `id` (UUID), `username`, `email`, para cubrir login por
        usuario o identificadores alineados con Supabase Auth.
        """
        if not subject or not str(subject).strip():
            return None
        subject = str(subject).strip()

        uid = _uuid_or_none(subject)
        if uid:
            row = await self._fetch_profile_row("id", uid)
            if row is not None:
                out = self._profile_row_to_user_out(row, subject=subject)
                return await self.attach_preferred_language(out) if out is not None else None

        for column in ("username", "email"):
            row = await self._fetch_profile_row(column, subject)
            if row is not None:
                out = self._profile_row_to_user_out(row, subject=subject)
                if out is not None:
                    return await self.attach_preferred_language(out)

        return None

    async def ensure_empresa_context(self, *, empresa_id: str | UUID) -> None:
        """
        Establece `app.current_empresa_id` / `app.empresa_id` vía RPC (PostgREST).

        Convocado tras resolver el usuario y **de nuevo antes de operaciones de escritura**
        (`deps.bind_write_context`) para reducir ventanas de contexto incorrecto entre
        peticiones concurrentes. Ver `docs/SECURITY_RLS_AND_TENANT_CONTEXT.md`.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            logger.warning("ensure_empresa_context: empresa_id vacío, RPC omitido")
            return
        try:
            await self._db.rpc("set_empresa_context", {"p_empresa_id": eid})
            logger.debug("Tenant context RPC ok (empresa_id prefix=%s…)", eid[:12])
        except Exception as exc:
            logger.warning("set_empresa_context RPC falló: %s", exc)

    async def ensure_rbac_context(self, *, user: UserOut) -> None:
        """Publica app.rbac_role, app.assigned_vehiculo_id y app.current_profile_id (RLS conductores)."""
        vid = user.assigned_vehiculo_id
        uid = user.usuario_id
        cid = user.cliente_id
        params: dict[str, object] = {
            "p_rbac_role": user.rbac_role,
            "p_assigned_vehiculo_id": str(vid) if vid is not None else None,
            "p_profile_id": str(uid) if uid is not None else None,
            "p_cliente_id": str(cid) if cid is not None else None,
        }
        try:
            await self._db.rpc("set_rbac_session", params)
        except Exception as exc:
            logger.warning("set_rbac_session RPC falló: %s", exc)

    async def try_set_empresa_context(self, *, empresa_id: str | UUID) -> None:
        """Alias retrocompatible de ``ensure_empresa_context``."""
        await self.ensure_empresa_context(empresa_id=empresa_id)

    async def set_password_for_username(self, *, username: str, new_plain_password: str) -> bool:
        """
        Persiste ``password_hash`` en Argon2id para el usuario canónico de ``usuarios``.
        Tras un JWT ``pwd_reset`` válido.
        """
        canon = (username or "").strip()
        if not canon:
            return False
        pwd = new_plain_password or ""
        if len(pwd) < 8:
            raise ValueError("password_too_short")
        u = await self.get_user(username=canon)
        if u is None:
            return False
        key = str(u.username or "").strip()
        if not key:
            return False
        new_hash = hash_password_argon2id(pwd)
        await self._db.execute(
            self._db.table("usuarios").update({"password_hash": new_hash}).eq("username", key)
        )
        logger.info("password_hash actualizado tras recuperación (usuario prefix=%s)", key[:48])
        return True

    async def get_usuario_email_for_notifications(self, *, username: str) -> str | None:
        """
        Devuelve ``usuarios.email`` si existe y parece un correo; usado para envío Resend
        cuando el login no es una dirección de correo.
        """
        key = (username or "").strip()
        if not key:
            return None
        try:
            q = self._db.table("usuarios").select("email").eq("username", key).limit(1)
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            logger.warning("get_usuario_email_for_notifications: %s", exc)
            return None
        if not rows:
            return None
        em = str(rows[0].get("email") or "").strip()
        if not em or not _NOTIFICATION_EMAIL_RE.match(em):
            return None
        return em.lower()

