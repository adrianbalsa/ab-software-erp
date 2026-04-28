from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api import deps
from app.schemas.auth import AuthErrorOut
from app.schemas.user import UserOut
from app.services.admin_usage_service import (
    AdminUsageService,
    CreditTransaction,
    TopUpResult,
)
from app.db.supabase import SupabaseAsync
from app.models.enums import UserRole

router = APIRouter(prefix="/credits", tags=["Admin - Credits"])
_COMMON_IAM_RESPONSES = {
    401: {"description": "No autenticado", "model": AuthErrorOut},
    403: {"description": "No autorizado", "model": AuthErrorOut},
}


class TopUpIn(BaseModel):
    tenant_id: str = Field(..., min_length=36, max_length=36)
    amount: int = Field(..., gt=0)
    reason: str = Field(default="Manual top-up", min_length=3, max_length=250)


class TopUpOut(BaseModel):
    tenant_id: str
    amount: int
    reason: str
    balance_after: int


class SyncOut(BaseModel):
    synced_tenants: int


class CreditTransactionOut(BaseModel):
    id: str
    tenant_id: str
    amount: int
    type: str
    description: str | None = None
    created_at: str


def _require_admin_or_superadmin(
    current_user: UserOut = Depends(deps.get_current_user),
) -> UserOut:
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPERADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin o superadmin",
        )
    return current_user


def _service(db: SupabaseAsync) -> AdminUsageService:
    return AdminUsageService(db)


@router.post("/top-up", response_model=TopUpOut, responses=_COMMON_IAM_RESPONSES)
async def top_up_credits(
    payload: TopUpIn,
    _admin: UserOut = Depends(_require_admin_or_superadmin),
    db: SupabaseAsync = Depends(deps.get_db_admin),
) -> TopUpOut:
    result: TopUpResult = await _service(db).top_up_credits(
        tenant_id=payload.tenant_id,
        amount=payload.amount,
        reason=payload.reason,
    )
    return TopUpOut(**result.__dict__)


@router.post("/sync", response_model=SyncOut, responses=_COMMON_IAM_RESPONSES)
async def sync_all_credits(
    _admin: UserOut = Depends(_require_admin_or_superadmin),
    db: SupabaseAsync = Depends(deps.get_db_admin),
) -> SyncOut:
    out = await _service(db).sync_all_credits()
    return SyncOut(synced_tenants=int(out.get("synced_tenants") or 0))


@router.get("/transactions", response_model=list[CreditTransactionOut], responses=_COMMON_IAM_RESPONSES)
async def list_credit_transactions(
    _admin: UserOut = Depends(_require_admin_or_superadmin),
    db: SupabaseAsync = Depends(deps.get_db_admin),
    tenant_id: str | None = Query(default=None, min_length=36, max_length=36),
    type: str | None = Query(default=None, pattern="^(TOPUP|USAGE|SYNC)$"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[CreditTransactionOut]:
    rows: list[CreditTransaction] = await _service(db).list_transactions(
        tenant_id=tenant_id,
        tx_type=type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [CreditTransactionOut(**row.__dict__) for row in rows]
