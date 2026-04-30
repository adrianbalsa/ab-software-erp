"""
Clasificación de km para reporting ESG y KPI de cobertura (datos primarios vs estimados).

Punto único de verdad para inferir ``esg_km_source`` y el km total usado en certificados GLEC
cuando existen varias fuentes en ``portes``.

Registro de fuentes (auditoría DD §2.2) — ``ESG_KM_SOURCE_REGISTRY``:
cada clave es un valor permitido en ``portes.esg_km_source``; ``infer_rule`` resume cómo se
asigna cuando el campo explícito es NULL o inválido.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from typing import Any, Final, Literal, TypedDict

EsgKmSource = Literal["route_api_meters", "recorded_road_km", "telemetry", "estimated"]

_VALID_SOURCES: Final[tuple[str, ...]] = ("route_api_meters", "recorded_road_km", "telemetry", "estimated")

HIGH_ESTIMATED_KM_SHARE_PCT: Final[float] = 15.0


class EsgKmSourceRule(TypedDict):
    label: str
    infer_rule: str
    operational_km: str


ESG_KM_SOURCE_REGISTRY: dict[str, EsgKmSourceRule] = {
    "route_api_meters": {
        "label": "Routes API (metros)",
        "infer_rule": "``real_distance_meters`` > 0 (prioridad tras fuente explícita válida).",
        "operational_km": "``km_reales`` si > 0; si no, ``real_distance_meters`` / 1000; si no, ``km_estimados``.",
    },
    "recorded_road_km": {
        "label": "Km carretera persistido",
        "infer_rule": "Sin metros válidos; ``km_reales`` > 0.",
        "operational_km": "Igual que arriba (operational_km_for_row).",
    },
    "telemetry": {
        "label": "Telemetría GPS",
        "infer_rule": "Sin metros ni km_reales válidos; ``telemetry_distance_km`` > 0.",
        "operational_km": "Igual que arriba.",
    },
    "estimated": {
        "label": "Solo estimación operativa",
        "infer_rule": "Sin señales de distancia positivas en las columnas anteriores.",
        "operational_km": "``km_estimados`` (>= 0).",
    },
}


def _float_pos(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def infer_esg_km_source(row: dict[str, Any]) -> EsgKmSource:
    """
    Determina la fuente de km a partir de columnas persistidas en ``portes``.

    Prioridad: ``esg_km_source`` explícito (si válido) > metros Routes API > km operativo
    > telemetría (reservado) > estimado.
    """
    raw = row.get("esg_km_source")
    if raw is not None:
        s = str(raw).strip()
        if s in _VALID_SOURCES:
            return s  # type: ignore[return-value]
    if _float_pos(row.get("real_distance_meters")) is not None:
        return "route_api_meters"
    if _float_pos(row.get("km_reales")) is not None:
        return "recorded_road_km"
    if _float_pos(row.get("telemetry_distance_km")) is not None:
        return "telemetry"
    return "estimated"


def operational_km_for_row(row: dict[str, Any]) -> float:
    """
    Km de actividad alineado con export ISO 14083 enmascarado: ``km_reales`` si > 0,
    si no km desde ``real_distance_meters``, si no ``km_estimados``.
    """
    kr = _float_pos(row.get("km_reales"))
    if kr is not None:
        return kr
    rm = _float_pos(row.get("real_distance_meters"))
    if rm is not None:
        return rm / 1000.0
    return max(0.0, float(row.get("km_estimados") or 0.0))


def resolve_total_km_for_glec_certificate(row: dict[str, Any]) -> float:
    """
    Km total de ruta para ``esg_certificate_co2_vs_euro_iii`` (misma prioridad que
    certificación: medición carretera > km operativo persistido > estimación).
    """
    rm = _float_pos(row.get("real_distance_meters"))
    if rm is not None:
        return rm / 1000.0
    kr = _float_pos(row.get("km_reales"))
    if kr is not None:
        return kr
    return max(0.0, float(row.get("km_estimados") or 0.0))


def km_coverage_breakdown(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """
    Retorna fracciones 0–100 de km por fuente (sobre suma de ``operational_km_for_row``).

    Keys: ``pct_km_route_api_meters``, ``pct_km_recorded_road_km``, ``pct_km_telemetry``,
    ``pct_km_estimated``, más ``total_km_activity``.
    """
    sums: dict[str, float] = {
        "route_api_meters": 0.0,
        "recorded_road_km": 0.0,
        "telemetry": 0.0,
        "estimated": 0.0,
    }
    total_activity = 0.0
    for r in rows:
        km = operational_km_for_row(r)
        total_activity += km
        src = infer_esg_km_source(r)
        sums[src] = sums.get(src, 0.0) + km

    if total_activity <= 0:
        return {
            "total_km_activity": 0.0,
            "pct_km_route_api_meters": 0.0,
            "pct_km_recorded_road_km": 0.0,
            "pct_km_telemetry": 0.0,
            "pct_km_estimated": 0.0,
        }

    def pct(key: str) -> float:
        return round((sums[key] / total_activity) * 100.0, 4)

    return {
        "total_km_activity": round(total_activity, 6),
        "pct_km_route_api_meters": pct("route_api_meters"),
        "pct_km_recorded_road_km": pct("recorded_road_km"),
        "pct_km_telemetry": pct("telemetry"),
        "pct_km_estimated": pct("estimated"),
    }


def explicit_estimated_overrides_distance_signals(row: dict[str, Any]) -> bool:
    """
    True si ``esg_km_source='estimated'`` explícito pese a haber distancia medida en columnas.
    Útil para auditoría (calidad / trazabilidad).
    """
    raw = row.get("esg_km_source")
    if raw is None or str(raw).strip() != "estimated":
        return False
    return (
        _float_pos(row.get("real_distance_meters")) is not None
        or _float_pos(row.get("km_reales")) is not None
        or _float_pos(row.get("telemetry_distance_km")) is not None
    )


def build_esg_quality_report(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """
    Reporte agregado de calidad ESG: cobertura por fuente, % km medido vs estimado, gaps.

    ``pct_measured_km_activity`` = suma de % de km de actividad no atribuidos a ``estimated``
    (peso por operational_km_for_row, coherente con el cierre mensual).
    """
    row_list = list(rows)
    cov = km_coverage_breakdown(row_list)
    counts = Counter(infer_esg_km_source(r) for r in row_list)
    by_src: dict[str, int] = {k: int(counts.get(k, 0)) for k in _VALID_SOURCES}

    pct_est = float(cov["pct_km_estimated"])
    pct_measured = round(
        float(cov["pct_km_route_api_meters"])
        + float(cov["pct_km_recorded_road_km"])
        + float(cov["pct_km_telemetry"]),
        4,
    )

    gaps: list[dict[str, str]] = []
    if row_list and pct_est >= HIGH_ESTIMATED_KM_SHARE_PCT:
        gaps.append(
            {
                "kind": "high_estimated_km_share",
                "detail": (
                    f"{pct_est:.1f}% del km de actividad está clasificado como estimated "
                    f"(umbral {HIGH_ESTIMATED_KM_SHARE_PCT:.0f}%)."
                ),
            }
        )

    override_n = sum(1 for r in row_list if explicit_estimated_overrides_distance_signals(r))
    if override_n > 0:
        gaps.append(
            {
                "kind": "explicit_estimated_with_distance_signals",
                "detail": (
                    f"{override_n} porte(s) con esg_km_source explícito «estimated» "
                    "pese a existir señales de distancia (revisar trazabilidad)."
                ),
            }
        )

    return {
        "km_coverage": cov,
        "pct_measured_km_activity": pct_measured,
        "pct_estimated_km_activity": round(pct_est, 4),
        "portes_by_source": by_src,
        "gaps": gaps,
    }


def esg_snapshot_content_sha256(payload: dict[str, Any]) -> str:
    """SHA-256 del JSON canónico del snapshot (debe coincidir con ``close_esg_period_snapshot``)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
