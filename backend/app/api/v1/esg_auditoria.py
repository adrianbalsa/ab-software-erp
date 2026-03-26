from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api import deps
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut

router = APIRouter(prefix="/esg")


class EsgAuditFuelMonthlyOut(BaseModel):
    mes: str = Field(..., description="YYYY-MM")
    litros_consumidos: float = Field(..., ge=0)
    co2_emitido_kg: float = Field(..., ge=0)
    co2_baseline_kg: float = Field(..., ge=0)
    co2_ahorro_kg: float = Field(..., ge=0)


class EsgAuditFuelAnnualOut(BaseModel):
    year: int
    empresa_id: str
    total_litros_consumidos: float = Field(..., ge=0)
    total_co2_emitido_kg: float = Field(..., ge=0)
    total_co2_baseline_kg: float = Field(..., ge=0)
    total_co2_ahorro_kg: float = Field(..., ge=0)
    meses: list[EsgAuditFuelMonthlyOut]


_CO2_KG_PER_LITRO_DIESEL_A = 2.67


@router.get(
    "/reporte-anual",
    response_model=EsgAuditFuelAnnualOut,
    status_code=status.HTTP_200_OK,
    summary="Reporte anual de combustible y CO₂ (auditoría)",
)
async def esg_reporte_anual_fuel(
    year: int = Query(date.today().year, ge=2000, le=2100),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> EsgAuditFuelAnnualOut:
    """
    Emisiones agregadas por mes para el Dashboard Económico (Scope fuel).

    - `co2_emitido_kg`: calculado con bonus Euro VI (si aplica) en importación de combustible.
    - `co2_baseline_kg`: litros × 2.67 kg CO2/L (sin bonus).
    - `co2_ahorro_kg`: baseline − emitido.
    """

    eid = str(current_user.empresa_id)
    if not eid.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empresa_id inválido"
        )

    fi = date(year, 1, 1).isoformat()
    ff = date(year, 12, 31).isoformat()

    q = filter_not_deleted(
        db.table("esg_auditoria")
        .select("fecha,litros_consumidos,co2_emitido_kg")
        .eq("empresa_id", eid)
        .gte("fecha", fi)
        .lte("fecha", ff)
    )

    res: Any = await db.execute(q)
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []

    # Acumuladores por mes (1..12)
    acc = {
        m: {
            "litros": 0.0,
            "co2_emitido": 0.0,
        }
        for m in range(1, 13)
    }

    for r in rows:
        raw_fecha = r.get("fecha")
        if raw_fecha is None:
            continue
        try:
            d = date.fromisoformat(str(raw_fecha))
        except ValueError:
            continue

        m = d.month
        litros = float(r.get("litros_consumidos") or 0.0)
        co2_emitido = float(r.get("co2_emitido_kg") or 0.0)
        acc[m]["litros"] += max(0.0, litros)
        acc[m]["co2_emitido"] += max(0.0, co2_emitido)

    meses_out: list[EsgAuditFuelMonthlyOut] = []
    total_litros = 0.0
    total_emitido = 0.0
    total_baseline = 0.0

    for m in range(1, 13):
        litros_m = acc[m]["litros"]
        co2_emitido_m = acc[m]["co2_emitido"]
        co2_baseline_m = litros_m * _CO2_KG_PER_LITRO_DIESEL_A
        co2_ahorro_m = max(0.0, co2_baseline_m - co2_emitido_m)

        total_litros += litros_m
        total_emitido += co2_emitido_m
        total_baseline += co2_baseline_m

        meses_out.append(
            EsgAuditFuelMonthlyOut(
                mes=f"{year}-{m:02d}",
                litros_consumidos=round(litros_m, 4),
                co2_emitido_kg=round(co2_emitido_m, 4),
                co2_baseline_kg=round(co2_baseline_m, 4),
                co2_ahorro_kg=round(co2_ahorro_m, 4),
            )
        )

    total_ahorro = max(0.0, total_baseline - total_emitido)

    return EsgAuditFuelAnnualOut(
        year=year,
        empresa_id=eid,
        total_litros_consumidos=round(total_litros, 4),
        total_co2_emitido_kg=round(total_emitido, 4),
        total_co2_baseline_kg=round(total_baseline, 4),
        total_co2_ahorro_kg=round(total_ahorro, 4),
        meses=meses_out,
    )

