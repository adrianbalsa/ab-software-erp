from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClienteBase(BaseModel):
    """Campos comunes de la tabla `clientes` (tenant-scoped)."""

    nombre: str = Field(..., min_length=1, max_length=255)
    nif: str | None = Field(default=None, max_length=20, description="CIF/NIF del cliente")
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=50)
    direccion: str | None = Field(default=None, max_length=500)


class ClienteCreate(ClienteBase):
    """Alta: `empresa_id` lo rellena el servicio desde el contexto de tenant."""

    model_config = ConfigDict(extra="ignore")


class ClienteOut(ClienteBase):
    """
    Respuesta API alineada con auditoría: PK y tenant como UUID, borrado lógico visible.
    """

    model_config = ConfigDict(extra="ignore")

    id: UUID
    empresa_id: UUID
    deleted_at: Optional[datetime] = Field(
        default=None,
        description="NULL = activo; timestamp = archivado (soft delete)",
    )
