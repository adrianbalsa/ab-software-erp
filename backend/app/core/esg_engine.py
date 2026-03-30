from __future__ import annotations

from typing import Final

# Factores simplificados por categoría EURO (kg CO2 / km).
_EMISSION_FACTORS_KG_PER_KM: Final[dict[str, float]] = {
    "EURO VI": 0.62,
    "EURO V": 0.68,
    "EURO IV": 0.74,
}


def _normalize_euro_key(raw: str) -> str:
    """Mapea etiquetas canónicas o legacy a claves internas (EURO IV|V|VI)."""
    s = str(raw or "").strip()
    if s in ("Euro IV", "Euro V", "Euro VI"):
        return "EURO " + s.split()[-1].upper()
    u = s.upper().replace("  ", " ").strip()
    if u in ("EURO IV", "EURO-IV", "EUROIV"):
        return "EURO IV"
    if u in ("EURO V", "EURO-V") or u == "EURO 5":
        return "EURO V"
    if u in ("EURO VI", "EURO-VI", "EURO 6"):
        return "EURO VI"
    return "EURO VI"


def resolve_normativa_euro_for_co2(
    *,
    normativa_euro: str | None = None,
    certificacion_emisiones: str | None = None,
) -> str:
    """
    Resuelve la etiqueta canónica ("Euro IV" | "Euro V" | "Euro VI") para ``calculate_co2_emissions``.

    Prioriza ``normativa_euro`` (columna dedicada). Si falta, infiere desde ``certificacion_emisiones``
    (Electrico / Hibrido → Euro VI como referencia de factor km para flota diésel estándar).
    """
    ne = (normativa_euro or "").strip()
    if ne in ("Euro IV", "Euro V", "Euro VI"):
        return ne
    cert = (certificacion_emisiones or "").strip()
    if cert == "Euro V":
        return "Euro V"
    if cert == "Euro VI":
        return "Euro VI"
    # Electrico / Hibrido / desconocido: factor más exigente (Euro VI) para kg/km genérico.
    return "Euro VI"


def calculate_co2_emissions(distancia_km: float, categoria_euro: str = "Euro VI") -> float:
    """
    Emisiones estimadas en kg CO2 para un porte.

    Args:
        distancia_km: Distancia recorrida en kilómetros.
        categoria_euro: Norma EURO del vehículo (ej: Euro VI, Euro V, Euro IV).
    """
    km = max(0.0, float(distancia_km or 0.0))
    cat = _normalize_euro_key(categoria_euro)
    factor = _EMISSION_FACTORS_KG_PER_KM.get(cat, _EMISSION_FACTORS_KG_PER_KM["EURO VI"])
    return round(km * factor, 6)
