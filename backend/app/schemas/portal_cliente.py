from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortalEsgResumenOut(BaseModel):
    """Métricas ESG visibles al cargador (ámbito propio, agregado YTD)."""

    co2_savings_ytd: float = Field(
        ...,
        description="kg CO₂ evitados acumulados año natural (GLEC / Euro III baseline)",
    )


class PortalPorteActivoListItem(BaseModel):
    id: UUID
    origen: str
    destino: str
    fecha: date | None = None
    estado: str = Field(..., description="Estado operativo del transporte")


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
    xml_verifactu_disponible: bool = Field(
        default=False,
        description="True si existe XML VeriFactu sellado exportable",
    )
