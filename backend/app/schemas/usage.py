from __future__ import annotations

from pydantic import BaseModel, Field


class MonthlyUsageMeterOut(BaseModel):
    meter: str = Field(
        ...,
        description="Medidor: maps_calls_month, ocr_pages_month o ai_tokens_month.",
    )
    used_units: int = Field(..., ge=0)
    limit_units: int = Field(..., ge=0)
    remaining_units: int = Field(..., ge=0)
    unit_label: str
    description: str
    capped: bool


class MonthlyUsageOut(BaseModel):
    empresa_id: str
    plan_type: str
    period_yyyymm: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    meters: list[MonthlyUsageMeterOut]
