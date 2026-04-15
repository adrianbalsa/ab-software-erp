from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.models.auth import UserRole

class UserInDB(BaseModel):
    """Fila `usuarios` (login legacy con hash)."""

    id: UUID | None = Field(
        default=None,
        description="PK `usuarios.id` (UUID); necesario para refresh tokens.",
    )
    username: str
    empresa_id: UUID
    rol: str
    password_hash: str


class UserOut(BaseModel):
    """
    Usuario autenticado tras validar JWT (Supabase o token API) y cargar `profiles`.

    `empresa_id` viene de `profiles.empresa_id` para filtrar datos por cliente.
    `usuario_id` es el `profiles.id` (UUID) cuando está disponible; trazabilidad en auditoría.
    """

    username: str
    empresa_id: UUID
    role: UserRole = Field(default=UserRole.GESTOR, description="Rol RBAC unificado")
    rol: str = Field(default="user", description="Rol legado panel admin (profiles.rol / usuarios.rol)")
    rbac_role: str = Field(
        default="owner",
        description="Rol RBAC operativo: owner | traffic_manager | driver | cliente | developer (profiles.role)",
    )
    cliente_id: UUID | None = Field(
        default=None,
        description="Maestro clientes (portal autoservicio) cuando rbac_role=cliente",
    )
    assigned_vehiculo_id: UUID | None = Field(
        default=None,
        description="Vehículo asignado al chófer (profiles.assigned_vehiculo_id)",
    )
    usuario_id: UUID | None = Field(
        default=None,
        description="Identificador de perfil (profiles.id) o None si solo hay login legacy",
    )
