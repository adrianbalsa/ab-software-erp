from __future__ import annotations

from typing import Any, Final

from fastapi import Depends, HTTPException, status

from app.api.auth_token import get_access_token
from app.api.deps import get_current_user
from app.core.security import decode_access_token_payload
from app.schemas.user import UserOut

_VALID_APP_ROLES: Final[frozenset[str]] = frozenset(
    {"owner", "admin", "driver", "traffic_manager", "cliente", "developer"}
)


def _normalize_app_role(raw: object) -> str | None:
    role = str(raw or "").strip().lower()
    if role in _VALID_APP_ROLES:
        return role
    return None


def _role_from_app_metadata(payload: dict[str, Any]) -> str | None:
    app_metadata = payload.get("app_metadata")
    if not isinstance(app_metadata, dict):
        return None
    return _normalize_app_role(app_metadata.get("role"))


def require_app_role(required_role: str):
    expected = _normalize_app_role(required_role)
    if expected is None:
        raise ValueError(f"Invalid app role: {required_role!r}")

    async def _dep(
        token: str = Depends(get_access_token),
        current_user: UserOut = Depends(get_current_user),
    ) -> UserOut:
        try:
            payload = decode_access_token_payload(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudo validar las credenciales",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        jwt_role = _role_from_app_metadata(payload)
        if jwt_role != expected:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return _dep
