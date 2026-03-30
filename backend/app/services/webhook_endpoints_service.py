from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status

from app.db.supabase import SupabaseAsync
from app.schemas.webhook_endpoint import (
    WebhookEndpointCreate,
    WebhookEndpointCreated,
    WebhookEndpointOut,
    WebhookEndpointSecretOut,
    WebhookEndpointUpdate,
)

_log = logging.getLogger(__name__)


def _eid(empresa_id: str | UUID) -> str:
    return str(empresa_id).strip()


def _validate_https_url(url: str) -> str:
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
    """32 caracteres hexadecimales (16 bytes aleatorios)."""
    return secrets.token_hex(16)


class WebhookEndpointsService:
    """CRUD ``public.webhook_endpoints`` con RLS (tenant); ``empresa_id`` desde el token."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_all(self, *, empresa_id: str | UUID) -> list[WebhookEndpointOut]:
        eid = _eid(empresa_id)
        res: Any = await self._db.execute(
            self._db.table("webhook_endpoints")
            .select("id, empresa_id, url, event_types, is_active, created_at")
            .eq("empresa_id", eid)
            .order("created_at", desc=True)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[WebhookEndpointOut] = []
        for r in rows:
            try:
                out.append(WebhookEndpointOut(**r))
            except Exception:
                _log.debug("webhook_endpoints list: fila omitida %s", r, exc_info=True)
        return out

    async def get_one(self, *, empresa_id: str | UUID, endpoint_id: str | UUID) -> WebhookEndpointOut:
        eid = _eid(empresa_id)
        wid = str(endpoint_id).strip()
        res: Any = await self._db.execute(
            self._db.table("webhook_endpoints")
            .select("id, empresa_id, url, event_types, is_active, created_at")
            .eq("id", wid)
            .eq("empresa_id", eid)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint no encontrado.")
        return WebhookEndpointOut(**rows[0])

    async def create(self, *, empresa_id: str | UUID, payload: WebhookEndpointCreate) -> WebhookEndpointCreated:
        eid = _eid(empresa_id)
        target = _validate_https_url(payload.url)
        secret = _generate_secret_key_32()
        body: dict[str, Any] = {
            "empresa_id": eid,
            "url": target,
            "secret_key": secret,
            "event_types": payload.event_types,
            "is_active": True,
        }
        q = self._db.table("webhook_endpoints").insert(body).select(
            "id, empresa_id, url, event_types, is_active, created_at"
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo crear el endpoint.",
            )
        row = dict(rows[0])
        return WebhookEndpointCreated(**row, secret_key=secret)

    async def update(
        self, *, empresa_id: str | UUID, endpoint_id: str | UUID, payload: WebhookEndpointUpdate
    ) -> WebhookEndpointOut:
        eid = _eid(empresa_id)
        wid = str(endpoint_id).strip()
        updates: dict[str, Any] = {}
        if payload.url is not None:
            updates["url"] = _validate_https_url(payload.url)
        if payload.event_types is not None:
            updates["event_types"] = payload.event_types
        if payload.is_active is not None:
            updates["is_active"] = payload.is_active
        if not updates:
            return await self.get_one(empresa_id=eid, endpoint_id=wid)
        res: Any = await self._db.execute(
            self._db.table("webhook_endpoints").update(updates).eq("id", wid).eq("empresa_id", eid).select(
                "id, empresa_id, url, event_types, is_active, created_at"
            )
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint no encontrado.")
        return WebhookEndpointOut(**rows[0])

    async def deactivate(self, *, empresa_id: str | UUID, endpoint_id: str | UUID) -> None:
        await self.update(empresa_id=empresa_id, endpoint_id=endpoint_id, payload=WebhookEndpointUpdate(is_active=False))

    async def get_secret(self, *, empresa_id: str | UUID, endpoint_id: str | UUID) -> WebhookEndpointSecretOut:
        eid = _eid(empresa_id)
        wid = str(endpoint_id).strip()
        res: Any = await self._db.execute(
            self._db.table("webhook_endpoints")
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
                detail="Endpoint no encontrado o inactivo.",
            )
        sk = str(rows[0].get("secret_key") or "")
        if not sk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Secreto no disponible.",
            )
        return WebhookEndpointSecretOut(secret_key=sk)
