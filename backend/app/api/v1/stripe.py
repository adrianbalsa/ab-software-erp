"""
Módulo estable para ``from app.api.v1 import stripe`` en ``app.main``.

El paquete pip ``stripe`` sigue importándose en ``endpoints/stripe_pago.py`` como ``import stripe``;
este módulo solo reexporta el router HTTP y no debe llamarse ``stripe`` en rutas internas ambiguas.
"""
from __future__ import annotations

from app.api.v1.endpoints.stripe_pago import router

__all__ = ["router"]
