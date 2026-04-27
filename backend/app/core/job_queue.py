"""
Punto único de importación para encolar trabajos asíncronos.

La implementación sigue siendo ARQ + Redis (`arq_queue`). Centralizar aquí las exportaciones
evita que el dominio importe directamente el broker y facilita un cambio futuro de cola
sin tocar servicios de facturación u otros callers.
"""

from __future__ import annotations

from app.core.arq_queue import (
    close_arq_redis_pool,
    enqueue_mark_legacy_sha256_passwords,
    enqueue_submit_to_aeat,
    get_arq_redis_pool,
)

__all__ = [
    "close_arq_redis_pool",
    "enqueue_mark_legacy_sha256_passwords",
    "enqueue_submit_to_aeat",
    "get_arq_redis_pool",
]
