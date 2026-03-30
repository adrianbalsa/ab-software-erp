"""Modelos de dominio (Pydantic) alineados con tablas Supabase."""

from app.models.vehiculo import NormativaEuro, Vehiculo
from app.models.webhook import WebhookEndpoint, WebhookEventType

__all__ = ["NormativaEuro", "Vehiculo", "WebhookEndpoint", "WebhookEventType"]
