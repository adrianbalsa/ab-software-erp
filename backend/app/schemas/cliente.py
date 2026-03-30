from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClienteBase(BaseModel):
    """Campos comunes de la tabla `clientes` (tenant-scoped)."""

    nombre: str = Field(..., min_length=1, max_length=255, description="Nombre o razón social del cliente", examples=["Logística del Sur S.L."])
    nif: str | None = Field(default=None, max_length=20, description="CIF/NIF del cliente válido según formato AEAT", examples=["B12345678"])
    email: str | None = Field(default=None, max_length=255, description="Correo electrónico de contacto (facturación/operaciones)", examples=["facturacion@logsur.com"])
    telefono: str | None = Field(default=None, max_length=50, description="Teléfono de contacto principal", examples=["+34 600 123 456"])
    direccion: str | None = Field(default=None, max_length=500, description="Dirección postal completa", examples=["Calle Principal 1, Polígono Industrial, 28001 Madrid"])


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
