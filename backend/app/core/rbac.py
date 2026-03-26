from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

AppRbacRole = Literal["owner", "traffic_manager", "driver", "cliente"]

VALID_ROLES: frozenset[str] = frozenset({"owner", "traffic_manager", "driver", "cliente"})


def normalize_rbac_role(
    profile_role: object,
    *,
    legacy_rol: object,
) -> AppRbacRole:
    """
    Prioridad: columna ``profiles.role`` (ENUM / texto). Fallback: ``profiles.rol`` legado
    (``admin`` → owner; resto → traffic_manager).
    """
    raw = profile_role
    if raw is not None:
        r = str(raw).strip().lower()
        if r in VALID_ROLES:
            return r  # type: ignore[return-value]
    lr = str(legacy_rol or "").strip().lower()
    if lr == "admin":
        return "owner"
    return "traffic_manager"


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _norm_role_str(raw: object) -> str:
    return str(raw or "").strip().upper()


def _roles_from_jwt_app_metadata(payload: dict[str, Any]) -> set[str]:
    roles: set[str] = set()

    app_md = payload.get("app_metadata")
    if isinstance(app_md, dict):
        if "role" in app_md and app_md.get("role") is not None:
            r = _norm_role_str(app_md.get("role"))
            if r:
                roles.add(r)

        # Supabase puede usar `roles` como lista (dependiendo de la configuración).
        if "roles" in app_md and app_md.get("roles") is not None:
            rv = app_md.get("roles")
            if isinstance(rv, list):
                for item in rv:
                    r = _norm_role_str(item)
                    if r:
                        roles.add(r)
            elif isinstance(rv, str):
                r = _norm_role_str(rv)
                if r:
                    roles.add(r)

    # Fallback por si el claim existe en otro sitio.
    # (Esto mantiene compatibilidad si en algún despliegue no se usó app_metadata.)
    top_role = payload.get("role")
    if top_role is not None:
        r = _norm_role_str(top_role)
        if r:
            roles.add(r)

    return roles


def _roles_from_legacy_rbac_claim(payload: dict[str, Any]) -> set[str]:
    """
    Fallback para tokens de esta API (claim `rbac_role`) mapeado a roles nuevos.

    Map (compatibilidad):
    - owner -> ADMIN
    - traffic_manager -> GESTOR
    - driver -> CONDUCTOR
    """

    out: set[str] = set()
    rr = payload.get("rbac_role")
    if rr is None:
        return out
    r = _norm_role_str(rr)
    mapping = {
        "OWNER": "ADMIN",
        "TRAFFIC_MANAGER": "GESTOR",
        "DRIVER": "CONDUCTOR",
    }
    mapped = mapping.get(r)
    if mapped:
        out.add(mapped)
    return out


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, token: str = Depends(_oauth2_scheme)) -> dict[str, Any]:
        """
        100% estricto:
        - Extrae `payload["app_metadata"]["role"]` (solo clave exacta `role`)
        - Si no hay rol o no está en `allowed_roles` -> 403
        """
        from app.core.security import decode_access_token_payload

        payload = decode_access_token_payload(token)

        # 1. Extraer app_metadata (100% estricto)
        app_metadata = payload.get("app_metadata", {}) or {}

        # 2. Extraer el rol (buscando solo la clave exacta 'role')
        user_role = app_metadata.get("role")

        if user_role and user_role in self.allowed_roles:
            return payload

        # 3. Tokens emitidos por POST /auth/login (claim `rbac_role`, sin app_metadata.role)
        if "ADMIN" in self.allowed_roles:
            rr = str(payload.get("rbac_role") or "").strip().lower()
            if rr == "owner":
                return payload

        if "GESTOR" in self.allowed_roles:
            rr = str(payload.get("rbac_role") or "").strip().lower()
            if rr == "traffic_manager":
                return payload

        if "CLIENTE" in self.allowed_roles:
            rr = str(payload.get("rbac_role") or "").strip().lower()
            if rr == "cliente":
                return payload
            am = payload.get("app_metadata")
            if isinstance(am, dict):
                ar = _norm_role_str(am.get("role"))
                if ar == "CLIENTE":
                    return payload

        # 4. Validación: sin rol permitido -> 403
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: Privilegios insuficientes.",
        )
