"""Constantes globales de producto (compliance, ESG, due diligence)."""

from __future__ import annotations

from typing import Final

# Factor diésel certificado — ISO 14083 (2021), well-to-wheel / auditoría comercial.
# Prohibido usar 2,5 u otros valores legacy en lógica de negocio sin actualizar este módulo.
ISO_14083_DIESEL_CO2_KG_PER_LITRE: Final[float] = 2.67

ISO_14083_REFERENCE_LABEL: Final[str] = (
    "ISO 14083:2021 — factor de referencia diésel 2,67 kg CO₂eq / L (auditoría / certificados)."
)
