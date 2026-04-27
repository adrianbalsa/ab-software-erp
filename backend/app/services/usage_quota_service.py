from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.core.plans import (
    CostMeter,
    fetch_empresa_plan,
    monthly_cost_quota,
    monthly_cost_quotas,
    normalize_plan,
)
from app.db.supabase import SupabaseAsync
from app.schemas.usage import MonthlyUsageMeterOut, MonthlyUsageOut


_METER_ALIASES: dict[str, CostMeter] = {
    "maps": CostMeter.MAPS,
    "ocr": CostMeter.OCR,
    "ai": CostMeter.AI,
}


def current_usage_period(today: date | None = None) -> str:
    d = today or datetime.now(timezone.utc).date()
    return f"{d.year:04d}-{d.month:02d}"


def normalize_cost_meter(meter: CostMeter | str) -> CostMeter:
    raw = str(meter or "").strip()
    if raw in _METER_ALIASES:
        return _METER_ALIASES[raw]
    return CostMeter(raw)


def estimate_ai_tokens(*parts: object, minimum: int = 1_000, output_reserve: int = 1_000) -> int:
    """
    Estimación conservadora para reservar cuota antes de llamar al proveedor LLM.

    No todos los SDKs devuelven usage antes del streaming; usamos ~4 chars/token
    más reserva de salida para que el hard cap siga siendo preventivo.
    """
    chars = 0
    for part in parts:
        if part is None:
            continue
        chars += len(str(part))
    estimated_input = max(1, (chars + 3) // 4)
    return max(int(minimum), estimated_input + max(0, int(output_reserve)))


@dataclass(frozen=True, slots=True)
class QuotaConsumption:
    empresa_id: str
    plan_type: str
    period_yyyymm: str
    meter: CostMeter
    used_units: int
    limit_units: int
    remaining_units: int


class UsageQuotaExceeded(HTTPException):
    def __init__(
        self,
        *,
        meter: CostMeter,
        used_units: int,
        limit_units: int,
        period_yyyymm: str,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "monthly_cost_quota_exceeded",
                "meter": meter.value,
                "period_yyyymm": period_yyyymm,
                "used_units": used_units,
                "limit_units": limit_units,
                "message": (
                    f"Cuota mensual agotada para {meter.value}: "
                    f"{used_units}/{limit_units} en {period_yyyymm}."
                ),
            },
        )


class UsageQuotaService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def consume(
        self,
        *,
        empresa_id: str,
        meter: CostMeter | str,
        units: int = 1,
        plan_type: str | None = None,
    ) -> QuotaConsumption:
        eid = str(empresa_id or "").strip()
        if not eid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empresa_id inválido")
        m = normalize_cost_meter(meter)
        n = max(1, int(units))
        plan = normalize_plan(plan_type or await fetch_empresa_plan(self._db, empresa_id=eid))
        quota = monthly_cost_quota(plan, m)
        period = current_usage_period()

        res: Any = await self._db.rpc(
            "consume_tenant_monthly_quota",
            {
                "p_empresa_id": eid,
                "p_period_yyyymm": period,
                "p_meter": m.value,
                "p_units": n,
                "p_limit_units": quota.limit_units,
            },
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        row = rows[0] if rows else None
        if not isinstance(row, dict):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo verificar la cuota mensual.",
            )

        used = int(row.get("used_units") or 0)
        limit = int(row.get("limit_units") or quota.limit_units)
        if not bool(row.get("allowed")):
            raise UsageQuotaExceeded(
                meter=m,
                used_units=used,
                limit_units=limit,
                period_yyyymm=period,
            )

        return QuotaConsumption(
            empresa_id=eid,
            plan_type=plan,
            period_yyyymm=period,
            meter=m,
            used_units=used,
            limit_units=limit,
            remaining_units=max(0, limit - used),
        )

    async def current_usage(self, *, empresa_id: str) -> MonthlyUsageOut:
        eid = str(empresa_id or "").strip()
        if not eid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empresa_id inválido")

        plan = normalize_plan(await fetch_empresa_plan(self._db, empresa_id=eid))
        period = current_usage_period()
        res: Any = await self._db.execute(
            self._db.table("tenant_monthly_usage")
            .select("meter,used_units,limit_units")
            .eq("empresa_id", eid)
            .eq("period_yyyymm", period)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        by_meter = {str(r.get("meter") or ""): r for r in rows}

        meters: list[MonthlyUsageMeterOut] = []
        for quota in monthly_cost_quotas(plan):
            row = by_meter.get(quota.meter.value) or {}
            used = max(0, int(row.get("used_units") or 0))
            limit = max(0, int(row.get("limit_units") or quota.limit_units))
            meters.append(
                MonthlyUsageMeterOut(
                    meter=quota.meter.value,
                    used_units=used,
                    limit_units=limit,
                    remaining_units=max(0, limit - used),
                    unit_label=quota.unit_label,
                    description=quota.description,
                    capped=used >= limit,
                )
            )

        return MonthlyUsageOut(
            empresa_id=eid,
            plan_type=plan,
            period_yyyymm=period,
            meters=meters,
        )
