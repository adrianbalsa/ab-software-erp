"""
Módulo estable para ``from app.api.v1 import stripe`` en ``app.main``.

El paquete pip ``stripe`` se importa en ``endpoints/stripe_pago.py``; el webhook canónico está en
``stripe_webhook.py`` (``POST /api/v1/webhooks/stripe``).
"""
from __future__ import annotations

from app.api.v1.endpoints.stripe_pago import router

__all__ = ["router"]
