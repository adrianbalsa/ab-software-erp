from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.plans import fetch_empresa_plan, max_facturas_mes, max_vehiculos, max_workspace_seats, normalize_plan
from app.db.supabase import SupabaseAsync
from app.schemas.empresa import EmpresaQuotaOut, WorkspaceMemberOut, WorkspaceTeamOut
from app.schemas.user import UserOut
from app.services import stripe_service
from app.services.flota_service import FlotaService
from app.services.facturas_service import FacturasService
from app.services.workspace_team_service import count_workspace_seated_profiles, list_workspace_members

router = APIRouter()


@router.get("/quota", response_model=EmpresaQuotaOut)
async def get_quota(
    current_user: UserOut = Depends(deps.get_current_user),
    db: SupabaseAsync = Depends(deps.get_db),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> EmpresaQuotaOut:
    eid = str(current_user.empresa_id)
    must_complete = False
    billing_suspended = False
    plan = await fetch_empresa_plan(db, empresa_id=eid)
    try:
        res: Any = await db.execute(
            db.table("empresas")
            .select("plan_type, requires_stripe_subscription, stripe_subscription_id, is_active")
            .eq("id", eid)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        rows = []
    if rows:
        row = rows[0]
        raw_pt = row.get("plan_type")
        if raw_pt is not None and str(raw_pt).strip():
            plan = normalize_plan(str(raw_pt))
        rq = row.get("requires_stripe_subscription") is True
        sid = row.get("stripe_subscription_id")
        sid_s = str(sid).strip() if sid else ""
        active = row.get("is_active") is not False
        billing_suspended = rq and not active
        must_complete = bool(rq and stripe_service.is_stripe_configured() and not sid_s)
    limit = max_vehiculos(plan)
    seat_limit = max_workspace_seats(plan)
    inv_limit = max_facturas_mes(plan)
    team_used = await count_workspace_seated_profiles(db, empresa_id=eid)
    fs = FlotaService(db)
    m = await fs.metricas_flota(empresa_id=eid)
    inv_used = 0
    if inv_limit is not None:
        inv_used = await facturas.count_facturas_emitidas_mes_calendario(empresa_id=eid)
    return EmpresaQuotaOut(
        plan_type=plan,
        must_complete_checkout=must_complete,
        billing_suspended=billing_suspended,
        limite_vehiculos=limit,
        vehiculos_actuales=m.total_vehiculos,
        limite_usuarios_equipo=seat_limit,
        usuarios_equipo_actuales=team_used,
        limite_facturas_mes=inv_limit,
        facturas_emitidas_mes_actual=inv_used,
    )


@router.get("/workspace-team", response_model=WorkspaceTeamOut)
async def get_workspace_team(
    _: UserOut = Depends(deps.require_role("owner", "developer")),
    current_user: UserOut = Depends(deps.get_current_user),
    db: SupabaseAsync = Depends(deps.get_db),
) -> WorkspaceTeamOut:
    eid = str(current_user.empresa_id)
    plan = await fetch_empresa_plan(db, empresa_id=eid)
    seat_limit = max_workspace_seats(plan)
    used = await count_workspace_seated_profiles(db, empresa_id=eid)
    raw_members = await list_workspace_members(db, empresa_id=eid)
    members = [WorkspaceMemberOut(id=m["id"], email=m["email"], rbac_role=m["rbac_role"]) for m in raw_members]
    return WorkspaceTeamOut(
        plan_type=plan,
        limite_usuarios_equipo=seat_limit,
        usuarios_equipo_actuales=used,
        members=members,
    )
