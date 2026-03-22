"""
Borrado lógico (`deleted_at IS NULL` = registro activo).

Tablas previstas: ``portes``, ``gastos``, ``flota`` (y ``vehiculos`` en BD si existe).

La migración ``20260319_fiscal_immutability_soft_delete_snapshot.sql`` añade la columna.
Los servicios filtran con ``.is_("deleted_at", "null")`` en lecturas y listados.
"""

from __future__ import annotations

from typing import Any

# Nombre de columna estándar en Supabase/Postgres
DELETED_AT_COLUMN = "deleted_at"


def filter_not_deleted(query: Any) -> Any:
    """
    Restringe una query PostgREST de Supabase a filas no borradas lógicamente.

    Uso: ``filter_not_deleted(db.table("portes").select("*").eq("empresa_id", eid))``
    """
    return query.is_(DELETED_AT_COLUMN, "null")


def soft_delete_payload() -> dict[str, str]:
    """Payload para marcar borrado lógico (timestamp lo pone Postgres con ``now()`` en SQL)."""
    # El cliente Supabase suele enviar ISO UTC desde Python:
    from datetime import datetime, timezone

    return {"deleted_at": datetime.now(timezone.utc).isoformat()}
