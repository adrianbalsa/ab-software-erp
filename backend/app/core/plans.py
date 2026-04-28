from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

# ─── Planes SaaS (AB Logistics OS) — catálogo Due Diligence 2026 ─────────────
# Slugs canónicos en BD (`empresas.plan_type`): starter | pro | enterprise
# Nombres comerciales: Compliance (antes Starter), Finance (antes Pro),
# Enterprise. Precios orientativos facturados vía Stripe
# (montos en EUR/mes IVA aparte según contrato).
#
# Compliance: 39€/mes — VeriFactu + CMR digital.
# Finance: 149€/mes — BI avanzado, conciliación bancaria e IA.
# Enterprise: 399€/mes — certificación ESG ISO 14083 continua y portal B2B.

PLAN_STARTER: Final[str] = "starter"
PLAN_PRO: Final[str] = "pro"
PLAN_ENTERPRISE: Final[str] = "enterprise"
PLAN_FREE: Final[str] = PLAN_STARTER

# EUR/mes (referencia producto; el cargo real lo define el Price en Stripe Dashboard)
EUR_MONTHLY_COMPLIANCE: Final[int] = 39
EUR_MONTHLY_FINANCE: Final[int] = 149
EUR_MONTHLY_FULL_STACK: Final[int] = 399

# Add-ons (líneas de ingreso adicionales)
ADDON_OCR_PACK: Final[str] = "ocr_pack"
ADDON_WEBHOOKS_B2B_PREMIUM: Final[str] = "webhooks_b2b_premium"
ADDON_LOGISADVISOR_IA_PRO: Final[str] = "logisadvisor_ia_pro"


class CostMeter(StrEnum):
    """Medidores facturables sujetos a hard cap mensual por tenant."""

    MAPS = "maps_calls_month"
    OCR = "ocr_pages_month"
    AI = "ai_tokens_month"

# Variables de entorno esperadas para Price IDs (producción / test en Dashboard Stripe)
ENV_STRIPE_PRICE_STARTER: Final[str] = "STRIPE_PRICE_STARTER"  # alias Due Diligence: STRIPE_PRICE_COMPLIANCE
ENV_STRIPE_PRICE_PRO: Final[str] = "STRIPE_PRICE_PRO"  # alias: STRIPE_PRICE_FINANCE
ENV_STRIPE_PRICE_ENTERPRISE: Final[str] = "STRIPE_PRICE_ENTERPRISE"  # alias: STRIPE_PRICE_FULL_STACK
ENV_STRIPE_PRICE_OCR_PACK: Final[str] = "STRIPE_PRICE_OCR_PACK"
ENV_STRIPE_PRICE_WEBHOOKS_B2B_PREMIUM: Final[str] = "STRIPE_PRICE_WEBHOOKS_B2B_PREMIUM"
ENV_STRIPE_PRICE_LOGISADVISOR_IA_PRO: Final[str] = "STRIPE_PRICE_LOGISADVISOR_IA_PRO"

# Product IDs (opcional; útil para catálogo, reporting y futuros syncs con Stripe)
ENV_STRIPE_PRODUCT_STARTER: Final[str] = "STRIPE_PRODUCT_STARTER"
ENV_STRIPE_PRODUCT_PRO: Final[str] = "STRIPE_PRODUCT_PRO"
ENV_STRIPE_PRODUCT_ENTERPRISE: Final[str] = "STRIPE_PRODUCT_ENTERPRISE"
ENV_STRIPE_PRODUCT_OCR_PACK: Final[str] = "STRIPE_PRODUCT_OCR_PACK"
ENV_STRIPE_PRODUCT_WEBHOOKS_B2B_PREMIUM: Final[str] = "STRIPE_PRODUCT_WEBHOOKS_B2B_PREMIUM"
ENV_STRIPE_PRODUCT_LOGISADVISOR_IA_PRO: Final[str] = "STRIPE_PRODUCT_LOGISADVISOR_IA_PRO"


@dataclass(frozen=True, slots=True)
class PlanFeatures:
    """Flags de producto por plan (referencia; enforcement en deps / rutas)."""

    verifactu: bool
    math_engine: bool  # EBITDA / motor financiero avanzado
    esg: bool
    max_vehiculos: int | None  # None = ilimitado


@dataclass(frozen=True, slots=True)
class BillingAddon:
    """Add-on de facturación recurrente (Stripe Billing)."""

    slug: str
    marketing_name: str
    eur_monthly: int
    description: str
    stripe_price_env: str
    stripe_product_env: str
    extra_ocr_documents_per_month: int | None


@dataclass(frozen=True, slots=True)
class MonthlyCostQuota:
    """Límite mensual de consumo para servicios con coste variable externo."""

    meter: CostMeter
    limit_units: int
    unit_label: str
    description: str


def billing_addons() -> tuple[BillingAddon, ...]:
    """Catálogo de add-ons; los `price_` / `product_` reales viven en variables de entorno."""
    return (
        BillingAddon(
            slug=ADDON_OCR_PACK,
            marketing_name="OCR Pack",
            eur_monthly=15,
            description="Hasta 500 documentos OCR adicionales al mes.",
            stripe_price_env=ENV_STRIPE_PRICE_OCR_PACK,
            stripe_product_env=ENV_STRIPE_PRODUCT_OCR_PACK,
            extra_ocr_documents_per_month=500,
        ),
        BillingAddon(
            slug=ADDON_WEBHOOKS_B2B_PREMIUM,
            marketing_name="Webhooks B2B Premium",
            eur_monthly=49,
            description="Webhooks salientes B2B de nivel premium (SLA y volumen ampliado).",
            stripe_price_env=ENV_STRIPE_PRICE_WEBHOOKS_B2B_PREMIUM,
            stripe_product_env=ENV_STRIPE_PRODUCT_WEBHOOKS_B2B_PREMIUM,
            extra_ocr_documents_per_month=None,
        ),
        BillingAddon(
            slug=ADDON_LOGISADVISOR_IA_PRO,
            marketing_name="LogisAdvisor IA Pro",
            eur_monthly=29,
            description="Capa IA avanzada de LogisAdvisor (planes inferiores a Enterprise).",
            stripe_price_env=ENV_STRIPE_PRICE_LOGISADVISOR_IA_PRO,
            stripe_product_env=ENV_STRIPE_PRODUCT_LOGISADVISOR_IA_PRO,
            extra_ocr_documents_per_month=None,
        ),
    )


def monthly_cost_quotas(plan_normalized: str) -> tuple[MonthlyCostQuota, ...]:
    """
    Cuotas mensuales de coste externo por plan.

    Unidades:
    - maps: llamadas facturables a Google Maps Platform (Routes/Distance/Geocoding no cacheadas).
    - ocr: páginas/documentos procesados con visión OCR.
    - ai: tokens estimados reservados antes de llamar al proveedor LLM.
    """
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return (
            MonthlyCostQuota(CostMeter.MAPS, 10_000, "llamadas", "Google Maps Platform"),
            MonthlyCostQuota(CostMeter.OCR, 2_000, "páginas", "OCR visión"),
            MonthlyCostQuota(CostMeter.AI, 5_000_000, "tokens", "IA / LogisAdvisor"),
        )
    if p == PLAN_PRO:
        return (
            MonthlyCostQuota(CostMeter.MAPS, 1_000, "llamadas", "Google Maps Platform"),
            MonthlyCostQuota(CostMeter.OCR, 200, "páginas", "OCR visión"),
            MonthlyCostQuota(CostMeter.AI, 1_000_000, "tokens", "IA / LogisAdvisor"),
        )
    return (
        MonthlyCostQuota(CostMeter.MAPS, 100, "llamadas", "Google Maps Platform"),
        MonthlyCostQuota(CostMeter.OCR, 20, "páginas", "OCR visión"),
        MonthlyCostQuota(CostMeter.AI, 100_000, "tokens", "IA / LogisAdvisor"),
    )


def monthly_cost_quota(plan_normalized: str, meter: CostMeter | str) -> MonthlyCostQuota:
    aliases = {"maps": CostMeter.MAPS, "ocr": CostMeter.OCR, "ai": CostMeter.AI}
    raw = str(meter)
    m = aliases[raw] if raw in aliases else CostMeter(raw)
    for quota in monthly_cost_quotas(plan_normalized):
        if quota.meter == m:
            return quota
    raise ValueError(f"Cost meter desconocido: {meter!r}")


def plan_marketing_name(plan_normalized: str) -> str:
    """Nombre comercial para UI / mensajes de error (el slug canónico sigue siendo técnico)."""
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return "Enterprise"
    if p == PLAN_PRO:
        return "Finance"
    return "Compliance"


def plan_list_eur_monthly(plan_normalized: str) -> int:
    """Precio de catálogo EUR/mes del plan base (referencia)."""
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return EUR_MONTHLY_FULL_STACK
    if p == PLAN_PRO:
        return EUR_MONTHLY_FINANCE
    return EUR_MONTHLY_COMPLIANCE


def normalize_plan(raw: str | None) -> str:
    """Normaliza valores en `empresas.plan_type` (mayúsculas, espacios, alias)."""
    s = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in ("", "starter", "start", "basic", "compliance"):
        return PLAN_STARTER
    if s in ("pro", "professional", "finance"):
        return PLAN_PRO
    if s in ("enterprise", "ent", "unlimited", "full_stack", "fullstack"):
        return PLAN_ENTERPRISE
    return PLAN_STARTER


def plan_requests_per_minute(plan_normalized: str) -> int:
    """
    RPM por plan para rate limiting de tráfico API.

    FREE/STARTER: base conservadora.
    PRO y ENTERPRISE incrementan capacidad.
    """
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return 600
    if p == PLAN_PRO:
        return 240
    return 60


def plan_initial_credits(plan_normalized: str) -> int:
    """
    Saldo base de créditos para servicios de coste alto (Maps/VeriFactu/AI).
    """
    p = normalize_plan(plan_normalized)
    if p == PLAN_ENTERPRISE:
        return 50_000
    if p == PLAN_PRO:
        return 10_000
    return 1_000


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
