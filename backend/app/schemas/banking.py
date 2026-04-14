"""
Modelos de dominio y DTOs HTTP para el módulo Banking (GoCardless + conciliación).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _parse_booked_fragment(val: str | date | datetime | None) -> str | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val.isoformat()[:10]
    if isinstance(val, datetime):
        return val.date().isoformat()
    s = str(val).strip()
    return s[:10] if s else None


class CuentaBancaria(BaseModel):
    """Cuenta enlazada en ``bank_accounts`` / GoCardless."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="UUID fila bank_accounts")
    gocardless_account_id: str
    institution_id: str | None = None
    iban_masked: str | None = None
    currency: str = "EUR"

    @classmethod
    def from_list_account_dict(cls, row: dict[str, Any]) -> Self:
        return cls(
            id=str(row.get("id") or ""),
            gocardless_account_id=str(row.get("gocardless_account_id") or ""),
            institution_id=row.get("institution_id"),
            iban_masked=row.get("iban_masked"),
            currency=str(row.get("currency") or "EUR")[:8],
        )


class Transaccion(BaseModel):
    """Movimiento bancario (``bank_transactions``) para motor de conciliación."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    amount: Decimal
    booked_date: str | date | datetime | None = None
    currency: str = "EUR"
    description: str | None = None
    remittance_info: str | None = None
    remittance_information: str | None = None
    reference: str | None = None
    concept: str | None = None
    concepto: str | None = None
    end_to_end_id: str | None = None
    empresa_id: str | None = None
    reconciled: bool | None = None
    internal_status: str | None = None

    def reference_blob(self) -> str:
        parts = [
            str(self.description or ""),
            str(self.reference or ""),
            str(self.concept or ""),
            str(self.concepto or ""),
            str(self.remittance_info or ""),
            str(self.remittance_information or ""),
            str(self.end_to_end_id or ""),
            str(self.transaction_id or ""),
        ]
        return " ".join(parts).casefold()

    @classmethod
    def from_bank_row(cls, row: dict[str, Any]) -> Self:
        tid = str(row.get("transaction_id") or "").strip()
        return cls(
            transaction_id=tid,
            amount=Decimal(str(row.get("amount") or "0")),
            booked_date=row.get("booked_date"),
            currency=str(row.get("currency") or "EUR")[:8],
            description=row.get("description"),
            remittance_info=row.get("remittance_info"),
            remittance_information=row.get("remittance_information"),
            reference=row.get("reference"),
            concept=row.get("concept"),
            concepto=row.get("concepto"),
            end_to_end_id=row.get("end_to_end_id"),
            empresa_id=str(row["empresa_id"]) if row.get("empresa_id") is not None else None,
            reconciled=row.get("reconciled"),
            internal_status=row.get("internal_status"),
        )

    def booked_date_iso(self) -> str | None:
        if self.booked_date is None:
            return None
        return _parse_booked_fragment(self.booked_date)


class FacturaConciliacion(BaseModel):
    """Factura candidata a emparejar con un movimiento (pendiente de cobro/pago)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    total_factura: Decimal
    numero_factura: str | None = None
    num_factura: str | None = None
    fecha_emision: str | date | datetime | None = None
    estado_cobro: str | None = None
    cliente: str | None = None
    cliente_nombre: str | None = None
    tipo_factura: str | None = None
    empresa_id: str | None = None

    def invoice_number(self) -> str:
        return str(self.numero_factura or self.num_factura or "").strip()

    def fecha_emision_iso(self) -> str | None:
        if self.fecha_emision is None:
            return None
        return _parse_booked_fragment(self.fecha_emision)

    @classmethod
    def from_factura_row(cls, row: dict[str, Any]) -> Self:
        return cls(
            id=int(row.get("id") or 0),
            total_factura=Decimal(str(row.get("total_factura") or "0")),
            numero_factura=row.get("numero_factura"),
            num_factura=row.get("num_factura"),
            fecha_emision=row.get("fecha_emision"),
            estado_cobro=row.get("estado_cobro"),
            cliente=str(row["cliente"]).strip() if row.get("cliente") is not None else None,
            cliente_nombre=row.get("cliente_nombre"),
            tipo_factura=row.get("tipo_factura"),
            empresa_id=str(row["empresa_id"]) if row.get("empresa_id") is not None else None,
        )


class ConciliationCandidate(BaseModel):
    """Resultado de un posible par movimiento ↔ factura (motor fuzzy + ventana de fechas)."""

    transaction_id: str
    factura_id: int
    score: float = Field(..., description="S_c combina referencia + fecha")
    reference_score: float
    date_score: float
    amount: float
    invoice_number: str | None = None
    booked_date: str | None = None
    invoice_date: str | None = None


class ConciliationMethod(str, Enum):
    """Origen de la decisión en la orquestación híbrida fuzzy + IA."""

    FUZZY_AUTO = "fuzzy_auto"
    AI = "ai"
    NONE = "none"


class ConciliationResult(BaseModel):
    """Resultado unificado por movimiento (fuzzy automático, IA o sin match)."""

    transaction_id: str
    method: ConciliationMethod
    final_confidence: float = Field(..., ge=0.0, le=1.0, description="Confianza final (fuzzy o IA).")
    candidate: ConciliationCandidate | None = None
    razonamiento_ia: str | None = Field(default=None, description="Solo si intervino la IA.")
    error: str | None = None


# --- HTTP DTOs (OpenAPI) ---


class BankingConnectOut(BaseModel):
    link: str
    requisition_id: str = Field(
        ...,
        description="ID de requisición GoCardless (persistido cifrado en servidor)",
    )


class BankingSyncOut(BaseModel):
    transacciones_procesadas: int
    coincidencias: int
    detalle: list[dict[str, Any]]


class BankingMovimientoOut(BaseModel):
    transaction_id: str
    booking_date: str = Field(..., description="Fecha contable ISO (YYYY-MM-DD)")
    amount: float
    currency: str
    remittance_info: str | None = None
    internal_status: str | None = None
    description: str | None = None


class BankingOAuthCompleteOut(BaseModel):
    requisition_id: str
    accounts: list[CuentaBancaria]
    transactions_imported: int
    transactions: list[BankingMovimientoOut]


BancoOAuthCompleteOut = BankingOAuthCompleteOut


class BankReconcileIn(BaseModel):
    commit: bool = Field(default=False, description="True: persistir conciliaciones en base de datos")
    threshold: float = Field(default=0.85, ge=0.5, le=1.0, description="Umbral mínimo S_c (modo batch sin IDs)")
    transaction_id: UUID | None = Field(
        default=None,
        description="Un solo movimiento a procesar con orquestador híbrido",
    )
    transaction_ids: list[UUID] | None = Field(
        default=None,
        description="Varios movimientos (procesados en paralelo con asyncio.gather)",
    )
    ai_commit_min_confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Si commit=True y el emparejamiento es por IA, solo persistir si confianza ≥ este valor",
    )

    @model_validator(mode="after")
    def _exclusive_transaction_lists(self) -> Self:
        if self.transaction_id is not None and self.transaction_ids is not None:
            raise ValueError("Indique solo transaction_id o transaction_ids, no ambos")
        return self


class BankReconcileOut(BaseModel):
    threshold_used: float
    commit: bool
    suggestions: list[ConciliationCandidate]
    committed_pairs: int
    hybrid_results: list[ConciliationResult] = Field(
        default_factory=list,
        description="Rellenado cuando se envían transaction_id(s) (orquestador híbrido)",
    )
    orchestration_mode: Literal["batch_fuzzy", "hybrid"] = Field(
        default="batch_fuzzy",
        description="batch_fuzzy: mismo comportamiento histórico sobre todos los pendientes",
    )


# Aliases retrocompatibles (schemas históricos)
BancoConectarOut = BankingConnectOut
BancoSyncOut = BankingSyncOut
BancoCuentaOut = CuentaBancaria
BancoMovimientoOut = BankingMovimientoOut
BancoOAuthCompleteOut = BankingOAuthCompleteOut
BankMatchSuggestionResult = ConciliationCandidate
BankAutoMatchIn = BankReconcileIn
BankAutoMatchOut = BankReconcileOut
