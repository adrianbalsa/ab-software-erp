from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DocumentExtraido(BaseModel):
    """Datos fiscales estructurados extraídos por visión LLM (Vampire Radar)."""

    proveedor_nombre: str | None = None
    nif_proveedor: str | None = None
    numero_documento: str | None = None
    fecha_documento: str | None = Field(
        default=None,
        description="Fecha del documento YYYY-MM-DD si consta",
    )
    base_imponible: float | None = None
    iva: float | None = None
    total: float | None = None
    moneda: str | None = Field(default="EUR", max_length=3)
    litros_combustible: float | None = None
    tipo_documento: Literal["ticket_combustible", "factura", "otro"] = "otro"
    ciudad_o_ubicacion: str | None = None
    requires_review: bool = False

    @field_validator("tipo_documento", mode="before")
    @classmethod
    def _coerce_tipo(cls, v: object) -> str:
        if v in ("ticket_combustible", "factura", "otro"):
            return str(v)
        return "otro"


class ProcessDocumentResponse(BaseModel):
    document: DocumentExtraido
    summary: str
    embedding_id: str | None = None
    cache_hit: bool = False


class AskAdvisorRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    match_count: int = Field(default=8, ge=1, le=30)


class AskAdvisorResponse(BaseModel):
    answer: str
    model: str | None = None
    sources: list[dict] = Field(
        default_factory=list,
        description="Fragmentos recuperados (id, similarity, metadata resumida)",
    )
