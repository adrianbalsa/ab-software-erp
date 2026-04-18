"""Enumeraciones y normalizadores centrales de dominio."""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """
    Roles RBAC unificados del sistema.
    """

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    GESTOR = "gestor"
    TRANSPORTISTA = "transportista"
    CLIENTE = "cliente"
    DEVELOPER = "developer"


def normalize_user_role(raw_role: object, *, legacy_role: object = None) -> UserRole:
    """
    Normaliza roles nuevos y legados hacia un único enum consistente.
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
