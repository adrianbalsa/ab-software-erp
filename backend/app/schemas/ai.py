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


class AiConsultRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    empresa_id: UUID | None = Field(
        default=None,
        description="Opcional: si se envía, debe coincidir con el tenant del JWT.",
    )
    data_context: dict | None = Field(
        default=None,
        description=(
            "Contexto opcional preconstruido con current_portes, financial_summary y maps_data. "
            "Si no se envía, el backend lo construye automáticamente."
        ),
    )


class AiConsultResponse(BaseModel):
    summary_headline: str
    profitability: dict
    fiscal_safety: dict
    liquidity: dict
    risk_flags: list = Field(default_factory=list)
    recommended_actions: list = Field(default_factory=list)
    model: str | None = None
    data_context: dict | None = None
