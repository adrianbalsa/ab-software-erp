from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.plans import fetch_empresa_plan, normalize_plan, plan_initial_credits
from app.db.supabase import SupabaseAsync
from app.services.usage_service import UsageService


@dataclass(frozen=True, slots=True)
class TopUpResult:
    tenant_id: str
    amount: int
    reason: str
    balance_after: int


@dataclass(frozen=True, slots=True)
class CreditTransaction:
    id: str
    tenant_id: str
    amount: int
    type: str
    description: str | None
    created_at: str


class AdminUsageService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db
        self._usage = UsageService(db=db)

    async def top_up_credits(self, tenant_id: str, amount: int, reason: str) -> TopUpResult:
        tid = str(tenant_id).strip()
        units = max(1, int(amount))
        why = str(reason or "Manual top-up").strip()
        redis = await self._usage._get_redis()
        if redis is not None:
            await redis.incrby(self._usage._credits_key(tid), units)
        res = await self._db.rpc(
            "record_tenant_credit_usage",
            {
                "p_empresa_id": tid,
                "p_units": units,
                "p_type": "TOPUP",
                "p_description": why,
            },
        )
        rows = (res.data or []) if hasattr(res, "data") else []
        row = rows[0] if rows else {}
        return TopUpResult(
            tenant_id=tid,
            amount=units,
            reason=why,
            balance_after=int(row.get("balance_after") or 0),
        )

    async def sync_all_credits(self) -> dict[str, int]:
        redis = await self._usage._get_redis()
        if redis is None:
            return {"synced_tenants": 0}
        synced = 0
        async for key in redis.scan_iter(match="usage:pending_sync:*", count=200):
            tenant_id = str(key).split("usage:pending_sync:", 1)[-1]
            pending = int(await redis.get(key) or 0)
            if pending <= 0:
                continue
            await self._db.rpc(
                "record_tenant_credit_usage",
                {
                    "p_empresa_id": tenant_id,
                    "p_units": pending,
                    "p_type": "SYNC",
                    "p_description": "Periodic Redis bucket sync",
                },
            )
            await redis.decrby(key, pending)
            synced += 1
        return {"synced_tenants": synced}

    async def check_low_credit_threshold(self, tenant_id: str) -> bool:
        tid = str(tenant_id).strip()
        plan = normalize_plan(await fetch_empresa_plan(self._db, empresa_id=tid))
        initial = max(1, int(plan_initial_credits(plan)))
        remaining = await self._usage.get_remaining_credits(tenant_id=tid, plan=plan)
        return remaining <= int(initial * 0.15)

    async def list_transactions(
        self,
        *,
        tenant_id: str | None = None,
        tx_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CreditTransaction]:
        q = self._db.table("credit_transactions").select(
            "id,tenant_id,amount,type,description,created_at"
        )
        if tenant_id:
            q = q.eq("tenant_id", str(tenant_id).strip())
        if tx_type:
            q = q.eq("type", str(tx_type).strip().upper())
        if start_date:
            q = q.gte("created_at", start_date.isoformat())
        if end_date:
            q = q.lte("created_at", end_date.isoformat())
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        res: Any = await self._db.execute(q)
        rows = (res.data or []) if hasattr(res, "data") else []
        out: list[CreditTransaction] = []
        for row in rows:
            out.append(
                CreditTransaction(
                    id=str(row.get("id") or ""),
                    tenant_id=str(row.get("tenant_id") or ""),
                    amount=int(row.get("amount") or 0),
                    type=str(row.get("type") or ""),
                    description=(str(row.get("description")) if row.get("description") is not None else None),
                    created_at=str(row.get("created_at") or ""),
                )
            )
        return out
