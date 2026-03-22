from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    nif_proveedor: str | None = Field(default=None, max_length=20)
    iva: float | None = Field(default=None, ge=0, description="Cuota de IVA en EUR (si consta en el ticket)")
    total_eur: float | None = Field(
        default=None,
        gt=0,
        description="Total documento en EUR (si no se informa y moneda=EUR, se usa total_chf)",
    )

    evidencia_url: str | None = None

    @field_validator("nif_proveedor", mode="before")
    @classmethod
    def _nif(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        return _normalize_nif(str(v))


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
    nif_proveedor: str | None = None
    iva: float | None = None
    total_eur: float | None = None
    deleted_at: datetime | None = None


class GastoOCRHint(BaseModel):
    """
    Hints desde Azure Document Intelligence (`prebuilt-invoice`).

    Mapeo típico: VendorName → proveedor, VendorTaxId → nif_proveedor,
    TotalTax → iva, InvoiceTotal (+ currency) → total / moneda.
    """

    proveedor: str | None = None
    fecha: date | None = None
    total: float | None = None
    moneda: str | None = None
    concepto: str | None = None
    nif_proveedor: str | None = None
    iva: float | None = None
