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


class BancoCuentaOut(BaseModel):
    id: str = Field(..., description="UUID fila ``bank_accounts``")
    gocardless_account_id: str
    institution_id: str | None = None
    iban_masked: str | None = None
    currency: str = "EUR"


class BancoMovimientoOut(BaseModel):
    transaction_id: str
    booking_date: str = Field(..., description="Fecha contable ISO (YYYY-MM-DD)")
    amount: float
    currency: str
    remittance_info: str | None = None
    internal_status: str | None = None
    description: str | None = None


class BancoOAuthCompleteOut(BaseModel):
    requisition_id: str
    accounts: list[BancoCuentaOut]
    transactions_imported: int
    transactions: list[BancoMovimientoOut]


class BankMatchSuggestionResult(BaseModel):
    transaction_id: str
    factura_id: int
    score: float = Field(..., description="S_c: confianza combinada referencia + fecha")
    reference_score: float
    date_score: float
    amount: float
    invoice_number: str | None = None
    booked_date: str | None = None
    invoice_date: str | None = None


class BankAutoMatchIn(BaseModel):
    commit: bool = Field(default=False, description="True: aplicar conciliación en base de datos")
    threshold: float = Field(default=0.85, ge=0.5, le=1.0, description="Umbral mínimo S_c para aceptar emparejamiento")


class BankAutoMatchOut(BaseModel):
    threshold_used: float
    commit: bool
    suggestions: list[BankMatchSuggestionResult]
    committed_pairs: int
