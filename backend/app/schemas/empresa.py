from __future__ import annotations

"""
Columnas Supabase/PostgREST: `nombre_legal`, `nombre_comercial` (snake_case).

- **Entrada (Create/Update):** se aceptan también claves JSON legacy sin guiones
  (`nombrelegal`, `nombrecomercial`) vía `validation_alias`.
- **Salida (EmpresaOut):** `id` y `empresa_id` son el mismo UUID (fila raíz tenant);
  `deleted_at` para borrado lógico alineado con auditoría D2/D3.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class EmpresaCreate(BaseModel):
    """Alta de empresa. Acepta JSON en snake_case o claves legacy sin guiones."""

    model_config = ConfigDict(populate_by_name=True)

    nif: str = Field(..., min_length=1, max_length=12, description="NIF o CIF de la empresa legal válido según AEAT", examples=["A12345678"])
    nombre_legal: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("nombre_legal", "nombrelegal"),
        description="Razón social registrada",
        examples=["AB Logistics Enterprise S.A."]
    )
    nombre_comercial: str | None = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("nombre_comercial", "nombrecomercial"),
        description="Nombre de la marca o comercial, si difiere del legal",
        examples=["AB Logistics"]
    )
    plan: str = Field(default="starter", min_length=1, max_length=50, description="Plan de suscripción (ej: starter, pro, enterprise)", examples=["pro"])
    email: str | None = Field(default=None, max_length=255, description="Correo electrónico oficial", examples=["contacto@ablogistics.com"])
    telefono: str | None = Field(default=None, max_length=50, description="Teléfono corporativo", examples=["+34 91 123 45 67"])
    direccion: str | None = Field(default=None, max_length=255, description="Sede o dirección principal", examples=["Av. Transporte 42, Planta 3"])
    iban: str | None = Field(
        default=None,
        max_length=34,
        description="IBAN bancario (se persiste cifrado en base de datos)",
        examples=["ES9121000418451234567890"]
    )
    activa: bool = True


class EmpresaUpdate(BaseModel):
    """Parcial. Acepta `nombre_comercial` o `nombrecomercial` en el cuerpo JSON."""

    model_config = ConfigDict(populate_by_name=True)

    plan: str | None = Field(default=None, min_length=1, max_length=50)
    activa: bool | None = None
    nombre_comercial: str | None = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("nombre_comercial", "nombrecomercial"),
    )
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=50)
    direccion: str | None = Field(default=None, max_length=255)
    iban: str | None = Field(
        default=None,
        max_length=34,
        description="IBAN; se cifra antes de guardar",
    )


class EmpresaOut(BaseModel):
    """
    Respuesta API: snake_case en JSON.
    En tabla `empresas`, `empresa_id` en el contrato API coincide con `id` (tenant raíz).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: UUID
    empresa_id: UUID
    nif: str
    nombre_legal: str
    nombre_comercial: str | None = None
    plan: str
    activa: bool
    fecha_registro: str | None = None
    email: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    iban: str | None = Field(
        default=None,
        max_length=34,
        description="IBAN en claro hacia el cliente (descifrado tras lectura BD)",
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        description="NULL = activa; timestamp = archivada (soft delete)",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_supabase_row(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "nombre_legal" not in out and "nombrelegal" in out:
            out["nombre_legal"] = out.pop("nombrelegal")
        if "nombre_comercial" not in out and "nombrecomercial" in out:
            out["nombre_comercial"] = out.pop("nombrecomercial")
        # Contrato uniforme: `empresa_id` = `id` si la fila no trae `empresa_id`
        if out.get("empresa_id") is None and out.get("id") is not None:
            out["empresa_id"] = out["id"]
        return out


class EmpresaQuotaOut(BaseModel):
    """Cuota de flota y plan normalizado para el tenant actual (JWT + RLS)."""

    plan_type: str
    limite_vehiculos: int | None = Field(
        default=None,
        description="None = Enterprise (sin tope); en otro caso coincide con plan_features.max_vehiculos.",
    )
    vehiculos_actuales: int
