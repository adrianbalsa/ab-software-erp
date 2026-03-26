from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortalPorteListItem(BaseModel):
    id: UUID
    origen: str
    destino: str
    fecha_entrega: datetime | None = Field(
        default=None,
        description="Marca hora de entrega firmada (POD)",
    )


class PortalFacturaListItem(BaseModel):
    id: int
    numero_factura: str
    fecha_emision: date
    total_factura: float
    estado_pago: str = Field(..., description="Pendiente | Pagada")
