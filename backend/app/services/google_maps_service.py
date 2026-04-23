from __future__ import annotations

from app.services.maps_service import MapsService


class GoogleMapsService(MapsService):
    """
    Alias explícito para compatibilidad con módulos que esperan
    `google_maps_service.py` durante la migración a Routes API v2.
    """

