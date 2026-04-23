from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db.supabase import SupabaseAsync

_log = logging.getLogger(__name__)


class VectorStoreService:
    """Inserción y búsqueda por similitud (coseno) sobre ``document_embeddings``."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def insert_document_embedding(
        self,
        *,
        empresa_id: str | UUID,
        content: str,
        metadata: dict[str, Any],
        embedding: list[float],
        source_sha256: str | None = None,
    ) -> str:
        if len(embedding) != 1536:
            raise ValueError(f"Se esperaban 1536 dimensiones de embedding, hay {len(embedding)}")

        row: dict[str, Any] = {
            "empresa_id": str(empresa_id),
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
        }
        if source_sha256:
            row["source_sha256"] = source_sha256

        res: Any = await self._db.execute(self._db.table("document_embeddings").insert(row))
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise RuntimeError("insert document_embeddings no devolvió filas")
        rid = rows[0].get("id")
        if not rid:
            raise RuntimeError("insert document_embeddings sin id")
        return str(rid)

    async def similarity_search(
        self,
        *,
        query_embedding: list[float],
        match_count: int = 8,
    ) -> list[dict[str, Any]]:
        if len(query_embedding) != 1536:
            raise ValueError(f"Se esperaban 1536 dimensiones, hay {len(query_embedding)}")

        res: Any = await self._db.rpc(
            "match_document_embeddings",
            {
                "p_query_embedding": query_embedding,
                "p_match_count": match_count,
            },
        )
        data = getattr(res, "data", None)
        if data is None and isinstance(res, list):
            return list(res)
        if isinstance(data, list):
            return data
        return []
