from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class Invoice(BaseModel):
    id: int | None = None
    empresa_id: UUID | None = None
    payment_status: PaymentStatus = PaymentStatus.PENDING
