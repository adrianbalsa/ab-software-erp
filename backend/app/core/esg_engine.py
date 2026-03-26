from __future__ import annotations

from typing import Final

# Factores simplificados por categoría EURO (kg CO2 / km).
_EMISSION_FACTORS_KG_PER_KM: Final[dict[str, float]] = {
    "EURO VI": 0.62,
    "EURO V": 0.68,
    "EURO IV": 0.74,
}


def calculate_co2_emissions(distancia_km: float, categoria_euro: str = "Euro VI") -> float:
    """
    Emisiones estimadas en kg CO2 para un porte.

    Args:
        distancia_km: Distancia recorrida en kilómetros.
        categoria_euro: Norma EURO del vehículo (ej: Euro VI, Euro V, Euro IV).
    """
    km = max(0.0, float(distancia_km or 0.0))
    cat = str(categoria_euro or "Euro VI").strip().upper()
    factor = _EMISSION_FACTORS_KG_PER_KM.get(cat, _EMISSION_FACTORS_KG_PER_KM["EURO VI"])
    return round(km * factor, 6)
