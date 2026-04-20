"""
Registro atómico de entregas de webhook por ``external_event_id`` para idempotencia.

Requiere la migración ``20260419203000_webhook_events_external_event_id.sql`` (índice único).
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.supabase import SupabaseAsync

_log = logging.getLogger(__name__)


def _is_unique_violation(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "duplicate key" in msg or "unique constraint" in msg:
        return True
    code = getattr(exc, "code", None)
    if code is not None and str(code) == "23505":
        return True
    details = getattr(exc, "details", None)
    if isinstance(details, str) and "duplicate key" in details.lower():
        return True
    return False


async def claim_webhook_event(
    db: SupabaseAsync,
    *,
    provider: str,
    external_event_id: str,
    event_type: str,
    payload: dict[str, Any],
    status: str = "PENDING",
) -> bool:
    """
    Inserta una fila en ``webhook_events`` con ``external_event_id``.

    Returns:
        True si esta entrega es la primera (claim OK).
        False si ya existía el par (provider, external_event_id) — entrega duplicada.
        True sin insertar si ``external_event_id`` está vacío (sin dedupe; compatibilidad).
    """
    ext = (external_event_id or "").strip()
    if not ext:
        return True

    prov = (provider or "").strip() or "unknown"
    et = (event_type or "unknown").strip()[:128] or "unknown"

    row: dict[str, Any] = {
        "provider": prov,
        "event_type": et,
        "payload": payload,
        "status": (status or "PENDING").strip()[:32] or "PENDING",
        "external_event_id": ext,
    }

    try:
        await db.execute(db.table("webhook_events").insert(row))
        return True
    except Exception as exc:
        if _is_unique_violation(exc):
            _log.info(
                "webhook idempotency: duplicate delivery provider=%s external_event_id=%s",
                prov,
                ext[:80],
            )
            return False
        raise


async def finalize_stripe_webhook_claim(
    db: SupabaseAsync,
    *,
    external_event_id: str,
    status: str = "COMPLETED",
) -> None:
    """Marca el claim Stripe como terminado (no participa en la cola GoCardless)."""
    ext = (external_event_id or "").strip()
    if not ext:
        return
    st = (status or "COMPLETED").strip()[:32] or "COMPLETED"
    await db.execute(
        db.table("webhook_events")
        .update({"status": st})
        .eq("provider", "stripe")
        .eq("external_event_id", ext)
    )


async def release_stripe_webhook_claim(db: SupabaseAsync, *, external_event_id: str) -> None:
    """Elimina el claim para permitir reintento tras error (Stripe reenvía el evento)."""
    ext = (external_event_id or "").strip()
    if not ext:
        return
    await db.execute(
        db.table("webhook_events").delete().eq("provider", "stripe").eq("external_event_id", ext)
    )
