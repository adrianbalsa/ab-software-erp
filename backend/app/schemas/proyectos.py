from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProyectoBase(BaseModel):
    """Campos comunes de la tabla `proyectos` (si existe en el proyecto)."""

    nombre: str = Field(..., min_length=1, max_length=255)
    codigo: str | None = Field(default=None, max_length=64, description="Código interno / referencia")
    descripcion: str | None = Field(default=None, max_length=4000)


class ProyectoCreate(ProyectoBase):
    """Alta: `empresa_id` lo rellena el servicio desde el tenant."""


class ProyectoOut(ProyectoBase):
    """Salida maestra: auditoría D2/D3 (UUID + soft delete)."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    empresa_id: UUID
    deleted_at: Optional[datetime] = Field(
        default=None,
        description="NULL = activo; timestamp = archivado",
    )
    # Referencia fiscal opcional (BIGINT)
    factura_id: int | None = Field(
        default=None,
        description="FK opcional a `facturas.id` (BIGINT)",
    )
