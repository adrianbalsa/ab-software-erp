from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UsuarioAdminOut(BaseModel):
    """Fila `usuarios` para panel admin (columnas opcionales según esquema real)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    username: str
    empresa_id: str
    rol: str = "user"
    activo: bool = True
    nombre_completo: str | None = None
    email: str | None = None
    fecha_creacion: str | None = Field(
        default=None,
        description="Alias de `created_at` si existe en la tabla",
    )


class UsuarioAdminPatch(BaseModel):
    rol: str | None = Field(default=None, min_length=1, max_length=50)
    activo: bool | None = None


class AuditoriaAdminRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    accion: str | None = None
    tabla: str | None = None
    registro_id: str | None = None
    empresa_id: str | None = None
    timestamp: str | None = None
    fecha: str | None = None
    cambios: object | None = None


class MetricasSaaSFacturacionOut(BaseModel):
    total_bruto: float
    total_iva: float
    ingreso_neto: float
    n_facturas: int
    arpu: float
