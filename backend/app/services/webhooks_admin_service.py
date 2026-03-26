from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status

from app.db.supabase import SupabaseAsync
from app.schemas.webhook_b2b import WebhookB2BCreated, WebhookB2BCreate, WebhookB2BOut, WebhookB2BSecretOut

_log = logging.getLogger(__name__)


def _eid(empresa_id: str | UUID) -> str:
    return str(empresa_id).strip()


def _validate_https_target_url(url: str) -> str:
    u = url.strip()
    p = urlparse(u)
    if p.scheme.lower() != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La URL de destino debe usar HTTPS.",
        )
    if not p.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL de destino inválida.",
        )
    return u


def _generate_secret_key_32() -> str:
    """32 caracteres hex (16 bytes aleatorios)."""
    return secrets.token_hex(16)


class WebhooksAdminService:
    """CRUD `public.webhooks` con RLS (owner); empresa_id siempre desde el token."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_active(self, *, empresa_id: str | UUID) -> list[WebhookB2BOut]:
        eid = _eid(empresa_id)
        res: Any = await self._db.execute(
            self._db.table("webhooks")
            .select("id, empresa_id, event_type, target_url, is_active, created_at")
            .eq("empresa_id", eid)
            .eq("is_active", True)
            .order("created_at", desc=True)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[WebhookB2BOut] = []
        for r in rows:
            try:
                out.append(WebhookB2BOut(**r))
            except Exception:
                _log.debug("webhooks list: fila omitida %s", r, exc_info=True)
        return out

    async def create(self, *, empresa_id: str | UUID, payload: WebhookB2BCreate) -> WebhookB2BCreated:
        eid = _eid(empresa_id)
        target = _validate_https_target_url(payload.target_url)
        secret = _generate_secret_key_32()
        body: dict[str, Any] = {
            "empresa_id": eid,
            "event_type": payload.event_type,
            "target_url": target,
            "secret_key": secret,
            "is_active": True,
        }
        q = self._db.table("webhooks").insert(body).select(
            "id, empresa_id, event_type, target_url, is_active, created_at"
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo crear el webhook.",
            )
        row = dict(rows[0])
        return WebhookB2BCreated(**row, secret_key=secret)

    async def deactivate(self, *, empresa_id: str | UUID, webhook_id: str | UUID) -> None:
        eid = _eid(empresa_id)
        wid = str(webhook_id).strip()
        res: Any = await self._db.execute(
            self._db.table("webhooks")
            .update({"is_active": False})
            .eq("id", wid)
            .eq("empresa_id", eid)
            .select("id")
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook no encontrado.",
            )

    async def get_secret(self, *, empresa_id: str | UUID, webhook_id: str | UUID) -> WebhookB2BSecretOut:
        eid = _eid(empresa_id)
        wid = str(webhook_id).strip()
        res: Any = await self._db.execute(
            self._db.table("webhooks")
            .select("secret_key")
            .eq("id", wid)
            .eq("empresa_id", eid)
            .eq("is_active", True)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook no encontrado o inactivo.",
            )
        sk = str(rows[0].get("secret_key") or "")
        if not sk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Secreto no disponible.",
            )
        return WebhookB2BSecretOut(secret_key=sk)
