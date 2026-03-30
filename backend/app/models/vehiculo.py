from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class NormativaEuro(StrEnum):
    """Normativa de emisiones EURO aplicable al factor CO₂ (kg/km) del motor ESG."""

    EURO_IV = "Euro IV"
    EURO_V = "Euro V"
    EURO_VI = "Euro VI"


class Vehiculo(BaseModel):
    """
    Vehículo de flota (tabla ``public.flota`` / ``public.vehiculos``).
    ``normativa_euro`` determina el factor en ``app.core.esg_engine``.
    """

    id: UUID | None = None
    empresa_id: UUID | None = None
    normativa_euro: NormativaEuro = Field(
        default=NormativaEuro.EURO_VI,
        description='Normativa EURO real para cálculo CO₂: "Euro IV", "Euro V" o "Euro VI".',
    )
