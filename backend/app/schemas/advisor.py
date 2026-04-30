from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID


class AdvisorAskIn(BaseModel):
    """Cuerpo de ``POST /api/v1/advisor/ask``."""

    message: str = Field(..., min_length=1, max_length=12000, description="Pregunta o instrucción para LogisAdvisor.")
    stream: bool = Field(
        default=True,
        description="Si es True, la respuesta es SSE (text/event-stream). Si es False, JSON con el texto completo.",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Sesión persistente del chat. Si falta, el backend crea una nueva.",
    )


class AdvisorAskOut(BaseModel):
    """Respuesta sin streaming (modo JSON opcional)."""

    reply: str
    model: str | None = None
    session_id: UUID | None = None
