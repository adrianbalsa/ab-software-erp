from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConciliacionSugerenciaLLM(BaseModel):
    """Una sugerencia validada (post-LLM y post-comprobación de IDs)."""

    movimiento_id: UUID
    factura_id: int = Field(..., description="PK bigint de facturas")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    razonamiento: str = Field(default="", max_length=4000)


class ConciliarAiOut(BaseModel):
    sugerencias_guardadas: int
    detalle: list[dict[str, Any]] = Field(default_factory=list)


class ConfirmarSugerenciaIn(BaseModel):
    movimiento_id: UUID
    aprobar: bool = Field(
        ...,
        description="True: conciliar (factura cobrada). False: rechazar sugerencia.",
    )


class MovimientoSugeridoOut(BaseModel):
    movimiento_id: UUID
    fecha: str
    concepto: str
    importe: float
    iban_origen: str | None
    factura_id: int | None
    confidence_score: float | None
    razonamiento_ia: str | None
    factura_numero: str | None = None
    factura_total: float | None = None
    factura_fecha: str | None = None
    cliente_nombre: str | None = None
