"""Resolución del JWT de la API: cabecera ``Authorization: Bearer`` o cookie HttpOnly."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


async def get_access_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        t = auth.split(" ", 1)[1].strip()
        if t:
            return t
    settings = get_settings()
    raw = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if raw and str(raw).strip():
        return str(raw).strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
