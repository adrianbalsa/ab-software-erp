from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookEventType(StrEnum):
    """Catálogo de eventos salientes (suscripción por tipo o comodín *)."""

    CREDIT_LIMIT_EXCEEDED = "credit.limit_exceeded"
    VERIFACTU_INVOICE_SIGNED = "verifactu.invoice_signed"
    ESG_CERTIFICATE_GENERATED = "esg.certificate_generated"
    ANALYTICS_PROFIT_MARGIN_SNAPSHOT = "analytics.profit_margin.snapshot"


class WebhookEndpoint(BaseModel):
    """Suscripción HTTP saliente por empresa (`public.webhook_endpoints`)."""

    id: UUID
    empresa_id: UUID
    url: str
    secret_key: str = Field(..., description="Secreto HMAC; solo se devuelve al crear o vía endpoint dedicado.")
    event_types: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime | None = None
