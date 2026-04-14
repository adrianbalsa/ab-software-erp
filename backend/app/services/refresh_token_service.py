from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_refresh_token
from app.core.user_agent_parser import humanize_user_agent, is_mobile_user_agent, truncate_ua
from app.db.supabase import SupabaseAsync
from app.schemas.auth import ActiveSessionOut
from app.schemas.user import UserOut
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


def _sentry_security_alert(message: str, **extra: Any) -> None:
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("security", "refresh_token_reuse")
            for k, v in extra.items():
                scope.set_extra(k, v)
            sentry_sdk.capture_message(message, level="error")
    except Exception:
        logger.error("%s | %s", message, extra)


def _parse_utc(ts: str | None) -> datetime | None:
    if not ts or not str(ts).strip():
        return None
    s = str(ts).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _session_row_is_active(row: dict[str, Any], *, now: datetime) -> bool:
    if bool(row.get("revoked")):
        return False
    exp = _parse_utc(str(row.get("expires_at") or ""))
    if exp is not None and exp < now:
        return False
    return True


class RefreshTokenService:
    """
    Rotación de refresh tokens: el token usado queda revocado; se emite uno nuevo.
    Reutilización de un token ya revocado (fuera de ventana de gracia) → alerta Sentry
    y revocación de todas las sesiones del usuario. [cite: 2026-03-22]
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    def _settings(self) -> Settings:
        return get_settings()

    async def _fetch_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        q = (
            self._db.table("refresh_tokens")
            .select("*")
            .eq("token_hash", token_hash)
            .limit(1)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return dict(rows[0]) if rows else None

    async def _fetch_by_id(self, row_id: str) -> dict[str, Any] | None:
        q = self._db.table("refresh_tokens").select("*").eq("id", row_id).limit(1)
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return dict(rows[0]) if rows else None

    async def revoke_all_for_user(self, *, user_id: str) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        try:
            await self._db.execute(
                self._db.table("refresh_tokens")
                .update({"revoked": True, "revoked_at": now})
                .eq("user_id", str(user_id))
            )
        except Exception as exc:
            logger.warning("revoke_all_for_user: %s", exc)

    async def issue_new_refresh(
        self,
        *,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, int]:
        """
        Inserta fila nueva y devuelve (token_plano_opaco, max_age_segundos).
        ``ip_address`` / ``user_agent`` se guardan para gestión de sesiones activas.
        """
        settings = self._settings()
        raw = secrets.token_urlsafe(48)
        th = hash_refresh_token(raw)
        now = datetime.now(tz=timezone.utc)
        expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        ip_s = (ip_address or "").strip()[:45] or None
        ua_s = truncate_ua(user_agent)
        payload: dict[str, Any] = {
            "user_id": str(user_id),
            "token_hash": th,
            "expires_at": expires.isoformat(),
            "revoked": False,
        }
        if ip_s:
            payload["ip_address"] = ip_s
        if ua_s:
            payload["user_agent"] = ua_s
        await self._db.execute(self._db.table("refresh_tokens").insert(payload))
        max_age = int((expires - now).total_seconds())
        return raw, max_age

    async def resolve_current_session_id(self, *, raw_refresh: str | None) -> str | None:
        """ID de la fila ``refresh_tokens`` válida asociada al token en cookie (si aplica)."""
        if not raw_refresh or not str(raw_refresh).strip():
            return None
        th = hash_refresh_token(raw_refresh.strip())
        row = await self._fetch_by_hash(th)
        if row is None:
            return None
        now = datetime.now(tz=timezone.utc)
        if not _session_row_is_active(row, now=now):
            return None
        rid = str(row.get("id") or "").strip()
        return rid or None

    async def list_active_sessions_as_out(
        self,
        *,
        user_id: str,
        current_session_id: str | None,
    ) -> list[ActiveSessionOut]:
        """Sesiones activas (no revocadas, no expiradas) del ``usuarios.id`` dado."""
        uid = str(user_id or "").strip()
        if not uid:
            return []
        now = datetime.now(tz=timezone.utc)
        now_iso = now.isoformat()
        try:
            q = (
                self._db.table("refresh_tokens")
                .select("id, user_agent, ip_address, created_at, expires_at, revoked")
                .eq("user_id", uid)
                .eq("revoked", False)
                .gt("expires_at", now_iso)
                .order("created_at", desc=True)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            logger.warning("list_active_sessions: %s", exc)
            return []

        out: list[ActiveSessionOut] = []
        for row in rows:
            if not _session_row_is_active(dict(row), now=now):
                continue
            sid = str(row.get("id") or "").strip()
            ua_raw = row.get("user_agent")
            ua_str = str(ua_raw) if ua_raw is not None else ""
            out.append(
                ActiveSessionOut(
                    id=sid,
                    device_type="mobile" if is_mobile_user_agent(ua_str) else "desktop",
                    client_summary=humanize_user_agent(ua_str if ua_str else None),
                    ip_address=str(row.get("ip_address") or "").strip() or None,
                    created_at=str(row.get("created_at") or ""),
                    is_current=bool(current_session_id and sid == current_session_id),
                )
            )
        return out

    async def revoke_session_for_user(self, *, session_id: str, user_id: str) -> bool:
        """
        Revoca una sesión concreta. Solo si ``refresh_tokens.user_id`` coincide con ``user_id``.
        """
        sid = str(session_id or "").strip()
        uid = str(user_id or "").strip()
        if not sid or not uid:
            return False
        row = await self._fetch_by_id(sid)
        if row is None or str(row.get("user_id") or "").strip() != uid:
            return False
        now = datetime.now(tz=timezone.utc).isoformat()
        try:
            await self._db.execute(
                self._db.table("refresh_tokens")
                .update({"revoked": True, "revoked_at": now})
                .eq("id", sid)
                .eq("user_id", uid)
                .eq("revoked", False)
            )
        except Exception as exc:
            logger.warning("revoke_session_for_user: %s", exc)
            return False
        return True

    async def revoke_all_for_user_except(
        self,
        *,
        user_id: str,
        except_session_id: str,
    ) -> int:
        """
        Revoca todas las sesiones activas del usuario salvo ``except_session_id``.
        Devuelve cuántas filas se intentaron revocar (best-effort).
        """
        uid = str(user_id or "").strip()
        keep = str(except_session_id or "").strip()
        if not uid or not keep:
            return 0
        now = datetime.now(tz=timezone.utc)
        now_iso = now.isoformat()
        try:
            q = (
                self._db.table("refresh_tokens")
                .select("id")
                .eq("user_id", uid)
                .eq("revoked", False)
                .gt("expires_at", now_iso)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            logger.warning("revoke_all_except list: %s", exc)
            return 0

        n = 0
        now_rev = datetime.now(tz=timezone.utc).isoformat()
        for row in rows:
            sid = str(row.get("id") or "").strip()
            if not sid or sid == keep:
                continue
            try:
                await self._db.execute(
                    self._db.table("refresh_tokens")
                    .update({"revoked": True, "revoked_at": now_rev})
                    .eq("id", sid)
                    .eq("user_id", uid)
                    .eq("revoked", False)
                )
                n += 1
            except Exception:
                continue
        return n

    def _within_grace(self, revoked_at_raw: str | None) -> bool:
        settings = self._settings()
        grace = settings.REFRESH_REUSE_GRACE_SECONDS
        if grace <= 0:
            return False
        revoked_at = _parse_utc(revoked_at_raw)
        if revoked_at is None:
            return False
        delta = (datetime.now(tz=timezone.utc) - revoked_at).total_seconds()
        return 0 <= delta < float(grace)

    async def _handle_reuse_attack(self, *, user_id: str) -> None:
        _sentry_security_alert(
            "Refresh token reutilizado (token revocado)",
            user_id=str(user_id),
        )
        await self.revoke_all_for_user(user_id=str(user_id))

    async def rotate(
        self,
        *,
        raw_refresh: str | None,
        auth_service: AuthService,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, int, UserOut]:
        """
        Valida cookie, rota refresh y devuelve
        (access_jwt, nuevo_refresh_plano, max_age_cookie, UserOut).
        """
        settings = self._settings()
        if not raw_refresh or not str(raw_refresh).strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta refresh token",
            )

        th = hash_refresh_token(raw_refresh.strip())
        row = await self._fetch_by_hash(th)
        now = datetime.now(tz=timezone.utc)
        now_iso = now.isoformat()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido",
            )

        user_id = str(row.get("user_id") or "")
        row_id = str(row.get("id") or "")
        revoked = bool(row.get("revoked"))
        exp = _parse_utc(str(row.get("expires_at") or ""))

        if revoked:
            if self._within_grace(str(row.get("revoked_at") or "")):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sesión ya renovada; vuelve a iniciar sesión si persiste el error",
                )
            await self._handle_reuse_attack(user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión invalidada por seguridad",
            )

        if exp is not None and exp < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expirado",
            )

        try:
            res_upd: Any = await self._db.execute(
                self._db.table("refresh_tokens")
                .update({"revoked": True, "revoked_at": now_iso})
                .eq("id", row_id)
                .eq("revoked", False)
            )
        except Exception as exc:
            logger.exception("Error revocando refresh en rotación: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo renovar la sesión",
            ) from exc

        updated_rows: list[dict[str, Any]] = (
            (res_upd.data or []) if hasattr(res_upd, "data") else []
        )
        if not updated_rows:
            row2 = await self._fetch_by_id(row_id)
            if row2 and row2.get("revoked"):
                if self._within_grace(str(row2.get("revoked_at") or "")):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Sesión ya renovada; vuelve a iniciar sesión si persiste el error",
                    )
                await self._handle_reuse_attack(user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido",
            )

        user_out = await auth_service.get_user_out_for_refresh(usuario_id=user_id)
        if user_out is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
            )

        new_raw, max_age = await self.issue_new_refresh(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        access = create_access_token(
            subject=user_out.username,
            empresa_id=user_out.empresa_id,
            role=user_out.role.value,
            rbac_role=user_out.rbac_role,
            assigned_vehiculo_id=str(user_out.assigned_vehiculo_id) if user_out.assigned_vehiculo_id else None,
            cliente_id=str(user_out.cliente_id) if user_out.cliente_id else None,
        )
        return access, new_raw, max_age, user_out
