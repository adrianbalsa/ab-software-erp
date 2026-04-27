from __future__ import annotations

from typing import Literal

AppRbacRole = Literal["owner", "traffic_manager", "driver", "cliente", "developer"]

VALID_ROLES: frozenset[str] = frozenset({"owner", "traffic_manager", "driver", "cliente", "developer"})


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
