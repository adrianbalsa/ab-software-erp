from __future__ import annotations

from typing import Any

from app.db.supabase import SupabaseAsync
from app.schemas.audit_log import AuditLogOut


class AuditLogsService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_for_empresa(
        self,
        *,
        empresa_id: str,
        limit: int = 100,
        table_name: str | None = None,
    ) -> list[AuditLogOut]:
        eid = str(empresa_id or "").strip()
        if not eid:
            return []
        lim = max(1, min(int(limit), 500))
        q: Any = (
            self._db.table("audit_logs")
            .select("*")
            .eq("empresa_id", eid)
            .order("created_at", desc=True)
        )
        if table_name and str(table_name).strip():
            q = q.eq("table_name", str(table_name).strip())
        q = q.limit(lim)
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[AuditLogOut] = []
        for row in rows:
            try:
                out.append(AuditLogOut.model_validate(row))
            except Exception:
                continue
        return out
