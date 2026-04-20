from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class GeoActivityPunto(BaseModel):
    """Un geostamp (origen o destino) asociado a un porte."""

    id_porte: UUID
    latitud: float = Field(..., ge=-90, le=90)
    longitud: float = Field(..., ge=-180, le=180)
    tipo_evento: Literal["entrega", "recogida"]
    margen_operativo: float | None = Field(
        default=None,
        description="Precio pactado menos gastos imputados al porte (EUR); null si el rol no tiene visibilidad de margen.",
    )


class GeoHeatCell(BaseModel):
    """Celda agregada para mapa de calor (densidad + ticket medio de gastos en la zona)."""

    latitud: float
    longitud: float
    intensidad: float = Field(..., ge=0, description="Peso normalizado 0–1 respecto a la celda más densa.")
    portes_en_celda: int = Field(..., ge=0)
    ticket_gasto_medio: float = Field(
        ...,
        ge=0,
        description="Importe medio (EUR) de tickets de gasto vinculados a portes con entrega en la celda.",
    )


class GeoActivityResponse(BaseModel):
    puntos: list[GeoActivityPunto]
    heatmap: list[GeoHeatCell] | None = Field(
        default=None,
        description="Solo para roles de explotación / administración; agregación por celda geográfica.",
    )
