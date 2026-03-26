from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WebhookB2BOut(BaseModel):
    """Suscripción B2B sin secret (listados)."""

    id: UUID
    empresa_id: UUID
    event_type: str
    target_url: str
    is_active: bool
    created_at: datetime


class WebhookB2BCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=200)
    target_url: str = Field(..., min_length=8, max_length=2000)

    @field_validator("event_type")
    @classmethod
    def strip_event(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("event_type requerido")
        return s

    @field_validator("target_url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()


class WebhookB2BCreated(WebhookB2BOut):
    """Respuesta al crear: incluye secret una sola vez."""

    secret_key: str = Field(..., min_length=32, max_length=64)


class WebhookB2BSecretOut(BaseModel):
    secret_key: str


class WebhookTestOut(BaseModel):
    """Resultado del ping de prueba (respuesta HTTP inmediata; envío en background)."""

    status: str = Field(default="queued", description="queued | sent (si sync en tests)")
