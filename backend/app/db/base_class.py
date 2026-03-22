"""
Convenciones de persistencia compartidas (sin ORM SQLAlchemy).

- Borrado lógico: columna ``deleted_at``; usar helpers en ``app.db.soft_delete``.
"""

from __future__ import annotations

from app.db.soft_delete import DELETED_AT_COLUMN, filter_not_deleted, soft_delete_payload

__all__ = ["DELETED_AT_COLUMN", "filter_not_deleted", "soft_delete_payload"]
