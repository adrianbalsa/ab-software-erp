from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

class AuditLogOut(BaseModel):
    """Fila de public.audit_logs expuesta al owner de la empresa."""

    model_config = {"extra": "ignore"}

    id: UUID
    empresa_id: UUID
    table_name: str
    record_id: str
    action: str  # INSERT/UPDATE/DELETE o extendidas (INVITE_SENT, …)
    old_data: dict[str, Any] | None = None
    new_data: dict[str, Any] | None = None
    changed_by: UUID | None = None
    created_at: datetime
