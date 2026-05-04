from __future__ import annotations

from typing import Any

from app.core.plans import fetch_empresa_plan, max_workspace_seats, normalize_plan, plan_marketing_name
from app.core.rbac import normalize_rbac_role
from app.db.supabase import SupabaseAsync


def _is_workspace_seat_row(row: dict[str, Any]) -> bool:
    """Cuenta usuarios de panel operativo (no portal B2B ni conductores)."""
    raw_cid = row.get("cliente_id")
    if raw_cid is not None and str(raw_cid).strip():
        return False
    rbac = normalize_rbac_role(row.get("role"), legacy_rol=row.get("rol"))
    return rbac in ("owner", "traffic_manager")


async def count_workspace_seated_profiles(db: SupabaseAsync, *, empresa_id: str) -> int:
    eid = str(empresa_id or "").strip()
    if not eid:
        return 0
    res: Any = await db.execute(
        db.table("profiles")
        .select("id,role,rol,cliente_id")
        .eq("empresa_id", eid),
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    return sum(1 for r in rows if isinstance(r, dict) and _is_workspace_seat_row(r))


async def list_workspace_members(db: SupabaseAsync, *, empresa_id: str) -> list[dict[str, Any]]:
    eid = str(empresa_id or "").strip()
    if not eid:
        return []
    res: Any = await db.execute(
        db.table("profiles")
        .select("id,email,username,role,rol,cliente_id")
        .eq("empresa_id", eid)
        .order("email", desc=False),
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict) or not _is_workspace_seat_row(r):
            continue
        rbac = normalize_rbac_role(r.get("role"), legacy_rol=r.get("rol"))
        email = str(r.get("email") or r.get("username") or "").strip()
        out.append(
            {
                "id": str(r.get("id") or "").strip(),
                "email": email,
                "rbac_role": rbac,
            }
        )
    return out


async def workspace_seat_usage(db: SupabaseAsync, *, empresa_id: str) -> tuple[int, int | None, str]:
    """
    Devuelve (ocupadas, límite o None, slug de plan normalizado).
    """
    plan = normalize_plan(await fetch_empresa_plan(db, empresa_id=empresa_id))
    limit = max_workspace_seats(plan)
    used = await count_workspace_seated_profiles(db, empresa_id=empresa_id)
    return used, limit, plan


def seat_limit_error_detail(*, used: int, limit: int, plan_slug: str) -> dict[str, Any]:
    return {
        "code": "workspace_seat_limit_exceeded",
        "used_seats": used,
        "limit_seats": limit,
        "plan_type": plan_slug,
        "plan_marketing_name": plan_marketing_name(plan_slug),
        "message": (
            f"Límite de usuarios del panel alcanzado para el plan {plan_marketing_name(plan_slug)} "
            f"({used}/{limit}). Mejora el plan o libera plazas."
        ),
    }
