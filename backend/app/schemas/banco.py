from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BancoConectarOut(BaseModel):
    """Enlace al flujo de autorización del banco (GoCardless)."""

    link: str
    requisition_id: str = Field(
        ...,
        description="ID de requisición GoCardless (también persistido cifrado en servidor)",
    )


class BancoSyncOut(BaseModel):
    transacciones_procesadas: int
    coincidencias: int
    detalle: list[dict[str, Any]]
