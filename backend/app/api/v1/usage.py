from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.schemas.usage import MonthlyUsageOut
from app.schemas.user import UserOut
from app.services.admin_usage_service import AdminUsageService, CreditTransaction
from app.services.usage_quota_service import UsageQuotaService
from app.db.supabase import SupabaseAsync

router = APIRouter(tags=["Uso y cuotas"])


@router.get("/usage", response_model=MonthlyUsageOut)
async def usage(
    current_user: UserOut = Depends(deps.get_current_active_user),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
) -> MonthlyUsageOut:
    """Consumo mensual del tenant frente a cuotas de Maps/OCR/IA por plan."""
    return await quotas.current_usage(empresa_id=str(current_user.empresa_id))


@router.get("/usage/my-transactions")
async def my_transactions(
    current_user: UserOut = Depends(deps.get_current_active_user),
    db: SupabaseAsync = Depends(deps.get_db),
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, object]]:
    """Ledger de transacciones de crédito del tenant autenticado."""
    svc = AdminUsageService(db)
    rows: list[CreditTransaction] = await svc.list_transactions(
        tenant_id=str(current_user.empresa_id),
        limit=max(1, min(500, int(limit))),
        offset=max(0, int(offset)),
    )
    return [row.__dict__ for row in rows]
