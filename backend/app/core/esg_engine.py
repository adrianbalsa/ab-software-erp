from __future__ import annotations

import re
from typing import Final

# Factores simplificados por categoría EURO (kg CO2 / km).
_EMISSION_FACTORS_KG_PER_KM: Final[dict[str, float]] = {
    "EURO VI": 0.62,
    "EURO V": 0.68,
    "EURO IV": 0.74,
    "EURO III": 0.82,
}

# Factores NOx por categoría EURO (g NOx / km).
# Referencia orientativa para auditoría interna (ajustable si se dispone de datos reales).
_NOX_FACTORS_G_PER_KM: Final[dict[str, float]] = {
    "EURO VI": 0.4,
    "EURO V": 2.0,
    "EURO IV": 3.5,
    "EURO III": 5.0,
}

# Factores dinámicos GLEC simplificados en gCO2/km por perfil.
# Convención: "<ENGINE_CLASS>_<FUEL_TYPE>_<LOAD>" donde LOAD es FULL o EMPTY.
_GLEC_GCO2_PER_KM: Final[dict[str, float]] = {
    "EURO_VI_DIESEL_FULL": 800.0,
    "EURO_VI_DIESEL_EMPTY": 550.0,
    "EURO_V_DIESEL_FULL": 860.0,
    "EURO_V_DIESEL_EMPTY": 600.0,
    "EURO_IV_DIESEL_FULL": 920.0,
    "EURO_IV_DIESEL_EMPTY": 650.0,
    "EURO_III_DIESEL_FULL": 980.0,
    "EURO_III_DIESEL_EMPTY": 700.0,
    "EV_ELECTRIC_FULL": 0.0,
    "EV_ELECTRIC_EMPTY": 0.0,
}


def _normalize_euro_key(raw: str) -> str:
    """Mapea etiquetas canónicas o legacy a claves internas (EURO IV|V|VI)."""
    s = str(raw or "").strip()
    if s in ("Euro III", "Euro IV", "Euro V", "Euro VI"):
        return "EURO " + s.split()[-1].upper()
    u = s.upper().replace("  ", " ").strip()
    if u in ("EURO III", "EURO-III", "EUROIII") or u == "EURO 3":
        return "EURO III"
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
    if ne in ("Euro III", "Euro IV", "Euro V", "Euro VI"):
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


def calculate_nox_emissions(distancia_km: float, categoria_euro: str = "Euro VI") -> float:
    """
    Emisiones estimadas en kg NOx para un porte.

    Args:
        distancia_km: Distancia recorrida en kilómetros.
        categoria_euro: Norma EURO del vehículo (ej: Euro VI, Euro V, Euro IV, Euro III).
    """
    km = max(0.0, float(distancia_km or 0.0))
    cat = _normalize_euro_key(categoria_euro)
    g_per_km = _NOX_FACTORS_G_PER_KM.get(cat, _NOX_FACTORS_G_PER_KM["EURO VI"])
    kg = (g_per_km * km) / 1000.0
    return round(kg, 6)


def get_co2_factor_kg_per_km(normativa_euro: str) -> float:
    """Factor CO₂ kg/km por normativa EURO."""
    key = _normalize_euro_key(normativa_euro)
    return _EMISSION_FACTORS_KG_PER_KM.get(key, _EMISSION_FACTORS_KG_PER_KM["EURO VI"])


def get_nox_factor_g_per_km(normativa_euro: str) -> float:
    """Factor NOx g/km por normativa EURO."""
    key = _normalize_euro_key(normativa_euro)
    return _NOX_FACTORS_G_PER_KM.get(key, _NOX_FACTORS_G_PER_KM["EURO VI"])


def _normalize_engine_class(raw: str | None) -> str:
    s = str(raw or "").strip().upper().replace("-", "_").replace(" ", "_")
    if s in {"EURO_VI", "EURO_V", "EURO_IV", "EURO_III", "EV"}:
        return s
    if s in {"ELECTRIC", "ELECTRICO", "ELÉCTRICO"}:
        return "EV"
    return "EURO_VI"


def _normalize_fuel_type(raw: str | None) -> str:
    s = str(raw or "").strip().upper().replace("-", "_").replace(" ", "_")
    if s in {"DIESEL", "ELECTRIC", "GASOLINA", "HIBRIDO"}:
        return s
    if s in {"ELÉCTRICO", "ELECTRICO", "EV"}:
        return "ELECTRIC"
    return "DIESEL"


def _factor_gco2_per_km(*, engine_class: str | None, fuel_type: str | None, load: str) -> float:
    ec = _normalize_engine_class(engine_class)
    ft = _normalize_fuel_type(fuel_type)
    key = f"{ec}_{ft}_{load}"
    if key in _GLEC_GCO2_PER_KM:
        return _GLEC_GCO2_PER_KM[key]
    # Fallbacks robustos para combinaciones no listadas.
    fb = f"{ec}_DIESEL_{load}"
    if fb in _GLEC_GCO2_PER_KM:
        return _GLEC_GCO2_PER_KM[fb]
    return _GLEC_GCO2_PER_KM["EURO_VI_DIESEL_EMPTY" if load == "EMPTY" else "EURO_VI_DIESEL_FULL"]


def esg_certificate_co2_vs_euro_iii(
    *,
    km_estimados: float,
    km_vacio: float | None,
    engine_class: str | None,
    fuel_type: str | None,
    subcontratado: bool,
) -> dict[str, float]:
    """
    Huella CO₂ del porte con el motor **GLEC** (``calculate_co2_footprint``) frente al mismo
    recorrido con motor de referencia **Euro III** (ISO 14001 / comparativas de flota).

    Returns:
        ``actual_total_kg``, ``euro_iii_baseline_kg``, ``ahorro_kg`` (≥ 0).
    """
    km_total = max(0.0, float(km_estimados or 0.0))
    km_v = max(0.0, float(km_vacio or 0.0))
    if km_v > km_total:
        km_v = km_total
    km_cargado = max(0.0, km_total - km_v)
    ec = engine_class or "EURO_VI"
    ft = fuel_type or "DIESEL"
    actual = calculate_co2_footprint(
        km_cargado=km_cargado,
        km_vacio=km_v,
        engine_class=ec,
        fuel_type=ft,
        subcontratado=subcontratado,
    )["total_co2_kg"]
    baseline = calculate_co2_footprint(
        km_cargado=km_cargado,
        km_vacio=km_v,
        engine_class="EURO_III",
        fuel_type=ft,
        subcontratado=subcontratado,
    )["total_co2_kg"]
    ahorro = max(0.0, float(baseline) - float(actual))
    return {
        "actual_total_kg": round(float(actual), 6),
        "euro_iii_baseline_kg": round(float(baseline), 6),
        "ahorro_kg": round(ahorro, 6),
    }


# Factores Euro VI operativos (kg CO₂ / km) por clase de MMA / articulado.
# Referencia auditoría: transporte pesado — barras típicas 0,70–0,90 kg/km según masa.
_EURO_VI_KG_CO2_PER_KM_WEIGHT_CLASS: Final[dict[str, float]] = {
    "LIGHT": 0.70,  # ≤ 3,5 t
    "MEDIUM": 0.78,  # ~ 7,5–12 t
    "HEAVY": 0.85,  # 18–26 t (rigids)
    "ARTIC": 0.90,  # +40 t / articulado
    "UNKNOWN": 0.82,
}


def infer_weight_class_from_vehicle_label(vehiculo: str | None) -> str:
    """
    Infiere clase de peso desde texto libre de ``flota.vehiculo`` (p. ej. «Scania 12t», «40Tn»).
    """
    raw = (vehiculo or "").strip().lower()
    if not raw:
        return "UNKNOWN"
    if any(
        k in raw
        for k in (
            "articulado",
            "artic",
            "mega",
            "roadtrain",
            "tractor",
        )
    ):
        return "ARTIC"
    m = re.search(r"(\d+[.,]?\d*)\s*(t|tn|ton)\b", raw)
    if m:
        try:
            t = float(m.group(1).replace(",", "."))
        except ValueError:
            t = 0.0
        if t <= 3.5:
            return "LIGHT"
        if t <= 12.0:
            return "MEDIUM"
        if t < 40.0:
            return "HEAVY"
        return "ARTIC"
    if "3.5" in raw or "3,5" in raw:
        return "LIGHT"
    if "12" in raw and "t" in raw:
        return "MEDIUM"
    if "40" in raw and ("t" in raw or "tn" in raw):
        return "ARTIC"
    return "UNKNOWN"


def euro_vi_factor_kg_per_km_for_weight_class(weight_class: str) -> float:
    """Factor kg CO₂/km (Euro VI) para la clase inferida."""
    k = (weight_class or "UNKNOWN").strip().upper()
    if k not in _EURO_VI_KG_CO2_PER_KM_WEIGHT_CLASS:
        k = "UNKNOWN"
    return float(_EURO_VI_KG_CO2_PER_KM_WEIGHT_CLASS[k])


def calculate_co2_footprint(
    *,
    km_cargado: float,
    km_vacio: float,
    engine_class: str | None = "EURO_VI",
    fuel_type: str | None = "DIESEL",
    subcontratado: bool = False,
) -> dict[str, float]:
    """
    Calcula CO2 dinámico por tramo cargado/vacío y clasifica Scope 1 vs Scope 3.

    Returns:
        {
          "total_co2_kg": float,
          "scope_1_kg": float,
          "scope_3_kg": float
        }
    """
    km_full = max(0.0, float(km_cargado or 0.0))
    km_empty = max(0.0, float(km_vacio or 0.0))
    f_full = _factor_gco2_per_km(engine_class=engine_class, fuel_type=fuel_type, load="FULL")
    f_empty = _factor_gco2_per_km(engine_class=engine_class, fuel_type=fuel_type, load="EMPTY")
    total_kg = ((km_full * f_full) + (km_empty * f_empty)) / 1000.0
    if subcontratado:
        return {
            "total_co2_kg": round(total_kg, 6),
            "scope_1_kg": 0.0,
            "scope_3_kg": round(total_kg, 6),
        }
    return {
        "total_co2_kg": round(total_kg, 6),
        "scope_1_kg": round(total_kg, 6),
        "scope_3_kg": 0.0,
    }
