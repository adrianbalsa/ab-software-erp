from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AiChatMessageIn(BaseModel):
    """Mensaje en el historial enviado por el cliente (solo user/assistant)."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=32000)


class AiChatRequest(BaseModel):
    """Cuerpo de `POST /ai/chat`."""

    message: str = Field(..., min_length=1, max_length=8000)
    history: list[AiChatMessageIn] = Field(
        default_factory=list,
        description="Turnos previos (máx. ~12 en servidor); el tenant no se confía del body.",
    )
    empresa_id: UUID | None = Field(
        default=None,
        description="Opcional: debe coincidir con el JWT; si no, se rechaza.",
    )


class AiChatResponse(BaseModel):
    reply: str
    model: str | None = None
