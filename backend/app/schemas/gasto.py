from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.security import fernet_encrypt_string


def _normalize_nif(value: str | None) -> str | None:
    if value is None:
        return None
    s = "".join(str(value).split()).upper()
    if not s:
        return None
    return s[:20]


class GastoCreate(BaseModel):
    proveedor: str = Field(..., min_length=1, max_length=255)
    fecha: date
    total_chf: float = Field(..., gt=0, description="Importe total del ticket (campo legacy; moneda según `moneda`)")
    categoria: str = Field(..., min_length=1, max_length=100)
    concepto: str | None = Field(default=None, max_length=2000)
    moneda: str = Field(default="EUR", min_length=3, max_length=3)

    # VeriFactu / trazabilidad fiscal (EUR)
    nif_proveedor: str | None = Field(
        default=None,
        max_length=512,
        description="NIF proveedor (entrada normalizada; se cifra para persistencia)",
    )
    iva: float | None = Field(default=None, ge=0, description="Cuota de IVA en EUR (si consta en el ticket)")
    total_eur: float | None = Field(
        default=None,
        gt=0,
        description="Total documento en EUR (si no se informa y moneda=EUR, se usa total_chf)",
    )

    evidencia_url: str | None = None
    porte_id: UUID | None = Field(
        default=None,
        description="Porte relacionado para imputación de margen real del viaje.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_and_encrypt_nif(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        raw = out.get("nif_proveedor")
        if raw is None or str(raw).strip() == "":
            out["nif_proveedor"] = None
            return out
        norm = _normalize_nif(str(raw))
        if not norm:
            out["nif_proveedor"] = None
            return out
        enc = fernet_encrypt_string(norm)
        out["nif_proveedor"] = enc if enc else None
        return out


class GastoOut(BaseModel):
    id: str
    empresa_id: UUID
    empleado: str
    proveedor: str
    fecha: date
    total_chf: float
    categoria: str
    concepto: str | None = None
    moneda: str
    evidencia_url: str | None = None
    porte_id: UUID | None = None
    nif_proveedor: str | None = None
    iva: float | None = None
    total_eur: float | None = None
    deleted_at: datetime | None = None


class GastoOCRHint(BaseModel):
    """
    Hints desde OCR de ticket (modelo de visión GPT‑4o / Gemini vía LiteLLM).

    Mapeo típico: nombre_gasolinera → proveedor, cif_emisor → nif_proveedor,
    iva/total/base_imponible del JSON estructurado.
    """

    proveedor: str | None = None
    fecha: date | None = None
    total: float | None = None
    moneda: str | None = None
    concepto: str | None = None
    nif_proveedor: str | None = None
    iva: float | None = None
    base_imponible: float | None = None
    litros_combustible: float | None = None
    ocr_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confianza agregada (0–1) si el proveedor la expone; con visión LLM suele ser null.",
    )
    requires_manual_review: bool = Field(
        default=False,
        description="True si el modelo marcó revisión, hay descuadre base+IVA vs total o datos dudosos.",
    )


class GastoOCRExtractOut(BaseModel):
    proveedor: str | None = None
    cif: str | None = None
    base_imponible: float | None = None
    iva: float | None = None
    total: float | None = None
    fecha: date | None = None
    litros: float | None = None
    requires_manual_review: bool = False
