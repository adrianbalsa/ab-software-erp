from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EsgPublicVerifyEmissions(BaseModel):
    co2_total_kg: float | None = None
    euro_iii_baseline_kg: float | None = None
    ahorro_vs_euro_iii_kg: float | None = None
    esg_total_km: float | None = None
    esg_portes_count: int | None = None
    iso_14083_diesel_kg_co2eq_per_litre: float = Field(default=2.67)


class EsgPublicVerifyOut(BaseModel):
    valid: bool
    found: bool = False
    certificate_id: str | None = None
    verification_status: str | None = None
    subject_type: str | None = None
    subject_id: str | None = Field(
        default=None,
        description="No expuesto en verificación pública (antes porte/factura); siempre null.",
    )
    certificate_content_sha256: str | None = None
    content_fingerprint_sha256: str | None = None
    pdf_sha256_matches: bool | None = None
    issued_at: datetime | None = None
    emissions: EsgPublicVerifyEmissions | None = None
    methodology_note: str | None = None
