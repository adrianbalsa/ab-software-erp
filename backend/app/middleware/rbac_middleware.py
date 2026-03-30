"""Middleware RBAC para control de acceso basado en roles."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from app.api import deps
from app.models.auth import UserRole
from app.schemas.user import UserOut


def requires_role(*allowed_roles: UserRole) -> Callable:
    """
    Decorador de dependencia FastAPI para proteger endpoints por rol RBAC.

    Uso:
        @router.get("/protected", dependencies=[Depends(requires_role(UserRole.ADMIN, UserRole.SUPERADMIN))])
        async def protected_endpoint():
            ...

    Args:
        *allowed_roles: Roles permitidos para acceder al endpoint

    Returns:
        Dependencia FastAPI que valida el rol del usuario

    Raises:
        HTTPException 403: Si el usuario no tiene un rol permitido
    """
    allowed_set = frozenset(allowed_roles)

    async def _role_checker(current_user: UserOut = Depends(deps.get_current_user)) -> UserOut:
        # Mapeo del rol operativo legado (rbac_role) a UserRole
        role_mapping = {
            "owner": UserRole.ADMIN,  # owner se considera ADMIN
            "traffic_manager": UserRole.STAFF,
            "driver": UserRole.STAFF,
            "developer": UserRole.ADMIN,
            "cliente": UserRole.STAFF,
        }

        # Intentar obtener el rol del usuario desde el nuevo campo 'role'
        # Si no existe, mapear desde rbac_role (compatibilidad hacia atrás)
        user_role = role_mapping.get(current_user.rbac_role, UserRole.STAFF)

        if user_role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de los siguientes roles: {', '.join(r.value for r in allowed_roles)}",
            )

        return current_user

    return _role_checker


def require_admin(current_user: UserOut = Depends(deps.get_current_user)) -> UserOut:
    """
    Dependencia FastAPI que requiere rol ADMIN o SUPERADMIN.

    Uso:
        @router.get("/admin-only")
        async def admin_endpoint(user: UserOut = Depends(require_admin)):
            ...
    """
    role_mapping = {
        "owner": UserRole.ADMIN,
        "developer": UserRole.ADMIN,
    }

    user_role = role_mapping.get(current_user.rbac_role, UserRole.STAFF)

    if user_role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de administrador.",
        )

    return current_user


def require_superadmin(current_user: UserOut = Depends(deps.get_current_user)) -> UserOut:
    """
    Dependencia FastAPI que requiere rol SUPERADMIN.

    Uso:
        @router.get("/superadmin-only")
        async def superadmin_endpoint(user: UserOut = Depends(require_superadmin)):
            ...
    """
    # En el modelo actual, no hay SUPERADMIN explícito
    # Se podría mapear desde un flag especial o username
    # Por ahora, solo owner con rol admin
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de superadministrador.",
        )

    return current_user
