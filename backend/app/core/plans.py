from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

# ─── Planes SaaS (AB Logistics OS) ───────────────────────────────────────────
# STARTER: 19€/mes, 5 vehículos, VeriFactu activo, ESG desactivado.
# PRO: 89€/mes, 25 vehículos, Math Engine activo, ESG desactivado.
# ENTERPRISE: 249€/mes, ilimitado, todo activo.

PLAN_STARTER: Final[str] = "starter"
PLAN_PRO: Final[str] = "pro"
PLAN_ENTERPRISE: Final[str] = "enterprise"


@dataclass(frozen=True, slots=True)
class PlanFeatures:
    """Flags de producto por plan (referencia; enforcement en deps / rutas)."""

    verifactu: bool
    math_engine: bool  # EBITDA / motor financiero avanzado
    esg: bool
    max_vehiculos: int | None  # None = ilimitado


def normalize_plan(raw: str | None) -> str:
    """Normaliza valores en `empresas.plan_type` (mayúsculas, espacios, alias)."""
    s = (raw or "").strip().lower()
    if s in ("", "starter", "start", "basic"):
        return PLAN_STARTER
    if s in ("pro", "professional"):
        return PLAN_PRO
    if s in ("enterprise", "ent", "unlimited"):
        return PLAN_ENTERPRISE
    return PLAN_STARTER


def plan_features(plan_normalized: str) -> PlanFeatures:
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return PlanFeatures(verifactu=True, math_engine=True, esg=True, max_vehiculos=None)
    if p == PLAN_PRO:
        return PlanFeatures(verifactu=True, math_engine=True, esg=False, max_vehiculos=25)
    return PlanFeatures(verifactu=True, math_engine=False, esg=False, max_vehiculos=5)


def max_vehiculos(plan_normalized: str) -> int | None:
    """None = sin tope (Enterprise)."""
    return plan_features(plan_normalized).max_vehiculos


async def fetch_empresa_plan(db: Any, *, empresa_id: str) -> str:
    """Lee `empresas.plan_type` con el cliente Supabase del JWT (RLS)."""
    q = db.table("empresas").select("plan_type").eq("id", str(empresa_id)).limit(1)
    res: Any = await db.execute(q)
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        return PLAN_STARTER
    row = rows[0]
    raw = row.get("plan_type")
    return normalize_plan(str(raw or ""))
