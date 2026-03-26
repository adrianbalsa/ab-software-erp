"""
Router HTTP de facturas bajo ``/api/v1/facturas`` (misma implementación que ``/facturas``).
"""

from __future__ import annotations

from app.api.routes.facturas import router

__all__ = ["router"]
