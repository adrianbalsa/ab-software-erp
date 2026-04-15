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
    GESTOR = "gestor"
    TRANSPORTISTA = "transportista"
    CLIENTE = "cliente"
    DEVELOPER = "developer"


def normalize_user_role(raw_role: object, *, legacy_role: object = None) -> UserRole:
    """
    Normaliza roles nuevos y legados hacia un único enum.
    """
    raw = str(raw_role or "").strip().lower()
    if raw in {r.value for r in UserRole}:
        return UserRole(raw)

    # Compatibilidad con roles operativos históricos
    if raw in {"owner"}:
        return UserRole.ADMIN
    if raw in {"traffic_manager"}:
        return UserRole.GESTOR
    if raw in {"driver"}:
        return UserRole.TRANSPORTISTA

    legacy = str(legacy_role or "").strip().lower()
    if legacy == "admin":
        return UserRole.ADMIN
    return UserRole.GESTOR


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


# --- CI/CD import compatibility layer (append-only surgical fix) ---
try:
    UserRole
except NameError:
    class UserRole(str, Enum):
        SUPERADMIN = "superadmin"
        ADMIN = "admin"
        STAFF = "staff"
        OWNER = "owner"
        TRAFFIC_MANAGER = "traffic_manager"
        DRIVER = "driver"
        CLIENTE = "cliente"
        DEVELOPER = "developer"


def normalize_user_role(
    role: str | None = None,
    legacy_role: str | None = None,
    **kwargs,
) -> str:
    """
    Normaliza un rol de usuario contra UserRole y devuelve siempre un valor string válido.
    Si no es válido, aplica fallback a "staff".
    """
    selected_role = role if role is not None else legacy_role
    normalized = (selected_role or "staff").strip().lower()
    if not normalized:
        return "staff"

    enum_values = {str(member.value).strip().lower() for member in UserRole}
    if normalized in enum_values:
        return normalized

    enum_name_to_value = {
        str(member.name).strip().lower(): str(member.value).strip().lower()
        for member in UserRole
    }
    return enum_name_to_value.get(normalized, "staff")
