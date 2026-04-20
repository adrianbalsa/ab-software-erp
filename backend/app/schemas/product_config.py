from __future__ import annotations

from pydantic import BaseModel, Field


class OperationalPricingOut(BaseModel):
    """Coste operativo de referencia expuesto al panel (€/km)."""

    coste_operativo_eur_km: float = Field(..., gt=0, description="Constante producto €/km (COSTE_OPERATIVO_EUR_KM).")
