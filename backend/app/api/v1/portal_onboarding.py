from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.core.risk_engine import RiskEngine
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.audit_logs_service import AuditLogsService

router = APIRouter()


async def _get_portal_cliente_row(*, db: SupabaseAsync, user: UserOut) -> dict[str, Any]:
    cliente_id = user.cliente_id
    if cliente_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta portal sin cliente vinculado",
        )
    res: Any = await db.execute(
        db.table("clientes")
        .select("*")
        .eq("id", str(cliente_id))
        .eq("empresa_id", str(user.empresa_id))
        .limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return rows[0]


@router.get("/onboarding/my-risk")
async def get_my_risk(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    db: SupabaseAsync = Depends(deps.get_db),
) -> dict[str, Any]:
    cliente = await _get_portal_cliente_row(db=db, user=portal_user)
    return RiskEngine.calculate_client_risk(cliente)


@router.post("/onboarding/accept-risk")
async def accept_risk(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    db: SupabaseAsync = Depends(deps.get_db),
) -> dict[str, Any]:
    cliente = await _get_portal_cliente_row(db=db, user=portal_user)
    risk_payload = RiskEngine.calculate_client_risk(cliente)
    cliente_id = str(cliente.get("id") or "")
    empresa_id = str(portal_user.empresa_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        await db.execute(
            db.table("clientes")
            .update({"riesgo_aceptado": True, "riesgo_aceptado_at": now_iso})
            .eq("id", cliente_id)
            .eq("empresa_id", empresa_id)
        )
    except Exception:
        # Compatibilidad con esquemas donde las columnas de onboarding no existan aun.
        pass

    audit = AuditLogsService(db)
    await audit.log_sensitive_action(
        empresa_id=empresa_id,
        table_name="clientes",
        record_id=cliente_id,
        action="RISK_ACCEPTED",
        old_value={
            "riesgo_aceptado": cliente.get("riesgo_aceptado"),
            "riesgo_aceptado_at": cliente.get("riesgo_aceptado_at"),
        },
        new_value={
            "riesgo_aceptado": True,
            "riesgo_aceptado_at": now_iso,
            "score": risk_payload.get("score"),
            "creditLimitEur": risk_payload.get("creditLimitEur"),
            "collectionTerms": risk_payload.get("collectionTerms"),
            "reasons": risk_payload.get("reasons") or [],
            "acceptance_text": (
                "Acepto mi evaluacion de riesgo y el sistema de cobro automatico "
                "SEPA como condicion para operar"
            ),
        },
        user_id=portal_user.usuario_id,
    )

    return {"status": "ok", "detail": "Aceptacion registrada"}

