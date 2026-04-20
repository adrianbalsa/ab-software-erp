from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.webhook import WebhookEventType


class WebhookEndpointOut(BaseModel):
    """Endpoint registrado (sin secret en listados)."""

    id: UUID
    empresa_id: UUID
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime | None = None


class WebhookEndpointCreate(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)
    event_types: list[str] = Field(
        ...,
        min_length=1,
        description="Tipos de evento o ['*'] para todos.",
    )

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()

    @field_validator("event_types")
    @classmethod
    def normalize_events(cls, v: list[str]) -> list[str]:
        out = [str(x).strip() for x in v if str(x).strip()]
        if not out:
            raise ValueError("event_types no puede estar vacío")
        return out


class WebhookEndpointUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    event_types: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("event_types")
    @classmethod
    def normalize_events(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out = [str(x).strip() for x in v if str(x).strip()]
        if not out:
            raise ValueError("event_types no puede estar vacío")
        return out


class WebhookEndpointCreated(WebhookEndpointOut):
    """Respuesta al crear: incluye secret_key una sola vez."""

    secret_key: str = Field(..., min_length=32, max_length=64)


class WebhookEndpointSecretOut(BaseModel):
    secret_key: str


class WebhookEndpointTestOut(BaseModel):
    status: str = Field(default="queued")


class WebhookEventCatalogOut(BaseModel):
    """Documentación de eventos soportados para integradores."""

    events: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"value": WebhookEventType.CREDIT_LIMIT_EXCEEDED.value, "description": "Hard stop por límite de crédito."},
            {
                "value": WebhookEventType.VERIFACTU_INVOICE_SIGNED.value,
                "description": "Factura firmada con XAdES correctamente.",
            },
            {
                "value": WebhookEventType.ESG_CERTIFICATE_GENERATED.value,
                "description": "Certificado / informe ESG mensual generado.",
            },
            {
                "value": WebhookEventType.ANALYTICS_PROFIT_MARGIN_SNAPSHOT.value,
                "description": "Serie agregada de margen / gastos (CSV o JSON) para cuadros de mando externos.",
            },
        ]
    )
