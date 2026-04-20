"""Constantes globales de producto (compliance, ESG, due diligence)."""

from __future__ import annotations

import os
from typing import Final


def _parse_positive_float(env_name: str, default: str) -> float:
    raw = (os.getenv(env_name) or default).strip()
    try:
        v = float(raw)
        return v if v > 0 else float(default)
    except ValueError:
        return float(default)


# Coste operativo de referencia €/km (mapas, BI proxy, advisor, IA). Override: COSTE_OPERATIVO_EUR_KM.
COSTE_OPERATIVO_EUR_KM: Final[float] = _parse_positive_float("COSTE_OPERATIVO_EUR_KM", "0.62")

# Factor diésel certificado — ISO 14083 (2021), well-to-wheel / auditoría comercial.
# Prohibido usar 2,5 u otros valores legacy en lógica de negocio sin actualizar este módulo.
ISO_14083_DIESEL_CO2_KG_PER_LITRE: Final[float] = 2.67

ISO_14083_REFERENCE_LABEL: Final[str] = (
    "ISO 14083:2021 — factor de referencia diésel 2,67 kg CO₂eq / L (auditoría / certificados)."
)
