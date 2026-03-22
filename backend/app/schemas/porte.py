from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cliente import ClienteOut


PorteEstado = Literal["pendiente", "facturado"]


class PorteCreate(BaseModel):
    cliente_id: UUID = Field(..., description="ID del cliente/cargador (FK clientes)")
    fecha: date = Field(..., description="Fecha de servicio")
    origen: str = Field(..., min_length=1, max_length=255)
    destino: str = Field(..., min_length=1, max_length=255)
    km_estimados: float = Field(default=0.0, ge=0)
    bultos: int = Field(default=1, ge=1)
    peso_ton: float | None = Field(
        default=None,
        ge=0,
        description="Peso de carga en toneladas (ESG); si no se envía, se estima desde bultos",
    )
    descripcion: str | None = Field(default=None, max_length=500)
    precio_pactado: float = Field(..., gt=0, description="Precio pactado en EUR")


class PorteOut(BaseModel):
    """Porte con FKs UUID; `cliente_detalle` opcional para respuestas enriquecidas."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    empresa_id: UUID
    cliente_id: UUID
    fecha: date
    origen: str
    destino: str
    km_estimados: float
    bultos: int
    descripcion: str | None
    precio_pactado: float
    co2_emitido: float | None = Field(
        default=None,
        description="kg CO2 estimados (Enterprise; distancia × toneladas × factor)",
    )
    peso_ton: float | None = Field(
        default=None,
        description="Toneladas de carga informadas (opcional)",
    )
    estado: PorteEstado
    factura_id: int | None = None
    deleted_at: datetime | None = None
    cliente_detalle: ClienteOut | None = Field(
        default=None,
        description="Opcional: maestro cliente (no viene de PostgREST en el SELECT * estándar)",
    )
