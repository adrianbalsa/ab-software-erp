from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InventarioItemBase(BaseModel):
    """Ítem de inventario / almacén (tabla maestra prevista)."""

    sku: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    unidad: str = Field(default="ud", max_length=20)
    stock: float = Field(default=0.0, ge=0)


class InventarioItemCreate(InventarioItemBase):
    """Alta: `empresa_id` lo rellena el servicio desde el tenant."""


class InventarioItemOut(InventarioItemBase):
    """Salida maestra: auditoría D2/D3."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    empresa_id: UUID
    deleted_at: Optional[datetime] = Field(
        default=None,
        description="NULL = activo; timestamp = archivado",
    )
    factura_id: int | None = Field(
        default=None,
        description="FK opcional a `facturas.id` (BIGINT)",
    )
