"""Modelos de autenticación y control de acceso basado en roles (RBAC)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import UserRole


class UserWithRole(BaseModel):
    """Usuario con rol RBAC para autenticación."""

    id: UUID
    username: str
    email: str | None = None
    empresa_id: UUID
    role: UserRole = Field(default=UserRole.GESTOR, description="Rol RBAC del usuario")
    rbac_role: str = Field(
        default="owner",
        description="Rol operativo legado (owner, traffic_manager, driver, cliente, developer)",
    )
