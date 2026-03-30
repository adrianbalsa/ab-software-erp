"""Modelos de autenticación y control de acceso basado en roles (RBAC)."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """
    Roles RBAC del sistema. Jerarquía:
    - SUPERADMIN: acceso total, gestión cross-tenant
    - ADMIN: gestión completa del tenant (finanzas, administración)
    - STAFF: operaciones básicas (portes, facturas, flota)
    """

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    STAFF = "staff"


class UserWithRole(BaseModel):
    """Usuario con rol RBAC para autenticación."""

    id: UUID
    username: str
    email: str | None = None
    empresa_id: UUID
    role: UserRole = Field(default=UserRole.STAFF, description="Rol RBAC del usuario")
    rbac_role: str = Field(
        default="owner",
        description="Rol operativo legado (owner, traffic_manager, driver, cliente, developer)",
    )
