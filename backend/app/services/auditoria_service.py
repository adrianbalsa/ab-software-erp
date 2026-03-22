from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db.supabase import SupabaseAsync


class AuditoriaService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def try_log(
        self,
        *,
        empresa_id: str,
        accion: str,
        tabla: str,
        registro_id: str,
        cambios: dict[str, Any],
    ) -> None:
        """
        Best-effort audit logging.

        Your current DB schema isn't guaranteed here; we avoid breaking core flows
        if the `auditoria` table has different columns.
        """
        payload: dict[str, Any] = {
            "empresa_id": empresa_id,
            "accion": accion,
            "tabla": tabla,
            "registro_id": registro_id,
            "cambios": json.dumps(cambios, ensure_ascii=False),
            # common timestamps seen across your codebase:
            "fecha": datetime.now(tz=timezone.utc).isoformat(),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        try:
            await self._db.execute(self._db.table("auditoria").insert(payload))
        except Exception:
            return

