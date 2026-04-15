from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ActiveSessionOut(BaseModel):
    """Sesión de refresh token activa (lista en UI de seguridad). [cite: 2026-03-22]"""

    id: str
    device_type: Literal["desktop", "mobile"] = Field(
        description="Tipo de dispositivo inferido del User-Agent",
    )
    client_summary: str = Field(
        description="Resumen legible, p. ej. 'Chrome en Windows'",
    )
    ip_address: str | None = None
    created_at: str = Field(description="ISO 8601 desde la BD")
    is_current: bool = Field(
        default=False,
        description="True si coincide con la cookie de refresh de esta petición",
    )


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = Field(
        default=None,
        description="Opaco de un solo uso; también se envía en cookie HttpOnly en /auth/login",
    )


class TokenPayload(BaseModel):
    sub: str
    exp: int
    iat: int | None = None
    empresa_id: str | None = Field(
        default=None,
        description="UUID de empresa (tokens firmados por esta API; Supabase Auth puede no incluirlo)",
    )


class OnboardingSetupIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    cif: str = Field(min_length=2, max_length=64)
    address: str = Field(min_length=5, max_length=255)
    initial_fleet_type: str = Field(min_length=2, max_length=120)
    target_margin_pct: float | None = Field(default=None, ge=0, le=100)


class OnboardingSetupOut(BaseModel):
    empresa_id: str
    profile_id: str
    role: str

