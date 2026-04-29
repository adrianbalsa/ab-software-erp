from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync


class ChatPersistenceService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def create_session(
        self,
        *,
        empresa_id: str,
        created_by_profile_id: str | None,
        title: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "empresa_id": empresa_id,
            "created_by_profile_id": created_by_profile_id,
            "title": (title or "").strip()[:200] or None,
        }
        res: Any = await self._db.execute(
            self._db.table("chat_sessions").insert(payload).select("*").limit(1)
        )
        rows = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("No se pudo crear la sesión de chat")
        return dict(rows[0])

    async def list_sessions(self, *, empresa_id: str, limit: int = 30) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit or 30), 100))
        res: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("chat_sessions")
                .select("id,empresa_id,title,created_at,updated_at,archived_at")
                .eq("empresa_id", empresa_id)
                .is_("archived_at", "null")
                .order("updated_at", desc=True)
                .limit(lim)
            )
        )
        return [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]

    async def get_session(self, *, empresa_id: str, session_id: UUID | str) -> dict[str, Any] | None:
        sid = str(session_id).strip()
        res: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("chat_sessions")
                .select("id,empresa_id,title,created_at,updated_at,archived_at")
                .eq("empresa_id", empresa_id)
                .eq("id", sid)
                .is_("archived_at", "null")
                .limit(1)
            )
        )
        rows = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return None
        return dict(rows[0])

    async def append_message(
        self,
        *,
        empresa_id: str,
        session_id: UUID | str,
        created_by_profile_id: str | None,
        role: str,
        content: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "empresa_id": empresa_id,
            "session_id": str(session_id).strip(),
            "created_by_profile_id": created_by_profile_id,
            "role": role,
            "content": content.strip(),
            "model": (model or "").strip() or None,
        }
        res: Any = await self._db.execute(
            self._db.table("chat_messages").insert(payload).select("*").limit(1)
        )
        rows = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("No se pudo guardar el mensaje del chat")
        # Touch de actividad de sesión.
        await self._db.execute(
            self._db.table("chat_sessions")
            .update({})
            .eq("empresa_id", empresa_id)
            .eq("id", str(session_id).strip())
        )
        return dict(rows[0])

    async def list_messages(
        self,
        *,
        empresa_id: str,
        session_id: UUID | str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit or 200), 500))
        res: Any = await self._db.execute(
            self._db.table("chat_messages")
            .select("id,session_id,role,content,model,created_at")
            .eq("empresa_id", empresa_id)
            .eq("session_id", str(session_id).strip())
            .order("created_at", desc=False)
            .limit(lim)
        )
        return [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]

    async def get_context_history(
        self,
        *,
        empresa_id: str,
        session_id: UUID | str,
        max_context_messages: int = 10,
        summary_char_budget: int = 1200,
    ) -> list[dict[str, str]]:
        """
        Historial compacto para el LLM:
        - Mantiene solo los ultimos N mensajes.
        - Si hay mas historial, agrega resumen sintetico de los mensajes antiguos.
        """
        sid = str(session_id).strip()
        res: Any = await self._db.execute(
            self._db.table("chat_messages")
            .select("role,content,created_at")
            .eq("empresa_id", empresa_id)
            .eq("session_id", sid)
            .order("created_at", desc=True)
            .limit(300)
        )
        rows = [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]
        rows.reverse()
        if not rows:
            return []

        max_n = max(1, min(int(max_context_messages or 10), 20))
        budget = max(300, min(int(summary_char_budget or 1200), 4000))

        if len(rows) <= max_n:
            return [
                {"role": str(r.get("role") or "user"), "content": str(r.get("content") or "")}
                for r in rows
                if str(r.get("content") or "").strip()
            ]

        older = rows[:-max_n]
        newer = rows[-max_n:]

        summary_lines: list[str] = []
        used = 0
        for r in older:
            role = str(r.get("role") or "user").strip().lower()
            content = " ".join(str(r.get("content") or "").split())
            if not content:
                continue
            line = f"- {role}: {content[:180]}"
            if used + len(line) > budget:
                break
            summary_lines.append(line)
            used += len(line)

        history: list[dict[str, str]] = []
        if summary_lines:
            history.append(
                {
                    "role": "system",
                    "content": (
                        "Resumen de mensajes anteriores (compresion para ahorro de tokens):\n"
                        + "\n".join(summary_lines)
                    ),
                }
            )

        history.extend(
            [
                {"role": str(r.get("role") or "user"), "content": str(r.get("content") or "")}
                for r in newer
                if str(r.get("content") or "").strip()
            ]
        )
        return history

    async def archive_inactive_sessions(
        self,
        *,
        empresa_id: str,
        inactive_days: int = 30,
    ) -> int:
        days = max(7, min(int(inactive_days or 30), 365))
        res: Any = await self._db.rpc(
            "archive_inactive_chat_sessions",
            {"p_empresa_id": empresa_id, "p_inactive_days": days},
        )
        if isinstance(res, int):
            return res
        if isinstance(res, dict) and "count" in res:
            return int(res["count"] or 0)
        return 0

    async def apply_retention_policy(
        self,
        *,
        empresa_id: str,
        retention_days: int = 180,
    ) -> int:
        days = max(30, min(int(retention_days or 180), 3650))
        res: Any = await self._db.rpc(
            "soft_delete_expired_chat_sessions",
            {"p_empresa_id": empresa_id, "p_retention_days": days},
        )
        if isinstance(res, int):
            return res
        if isinstance(res, dict) and "count" in res:
            return int(res["count"] or 0)
        return 0
