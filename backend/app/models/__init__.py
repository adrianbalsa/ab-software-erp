"""Modelos de dominio (Pydantic) alineados con tablas Supabase."""

from app.models.auth import UserWithRole
from app.models.enums import UserRole
from app.models.invoice import Invoice, PaymentStatus
from app.models.vehiculo import NormativaEuro, Vehiculo
from app.models.webhook import WebhookEndpoint, WebhookEventType

__all__ = [
    "NormativaEuro",
    "Vehiculo",
    "Invoice",
    "PaymentStatus",
    "WebhookEndpoint",
    "WebhookEventType",
    "UserRole",
    "UserWithRole",
]
