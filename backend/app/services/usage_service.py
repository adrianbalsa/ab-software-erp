from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.plans import normalize_plan, plan_initial_credits
from app.db.supabase import SupabaseAsync
from app.services.notification_service import send_alert

_log = logging.getLogger(__name__)

_USAGE_LUA = """
local credits_key = KEYS[1]
local pending_key = KEYS[2]
local amount = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', credits_key) or '0')
if current < amount then
  return {0, current}
end
local remaining = redis.call('DECRBY', credits_key, amount)
redis.call('INCRBY', pending_key, amount)
return {1, remaining}
"""


@dataclass(frozen=True, slots=True)
class UsageResult:
    allowed: bool
    remaining_credits: int


class UsageService:
    """
    Bucket de créditos por tenant con persistencia diferida en Postgres.
    """

    _redis_client: Any | None = None
    _redis_lock = asyncio.Lock()

    def __init__(self, db: SupabaseAsync | None = None) -> None:
        self._db = db

    @classmethod
    async def _get_redis(cls) -> Any | None:
        if cls._redis_client is not None:
            return cls._redis_client
        async with cls._redis_lock:
            if cls._redis_client is not None:
                return cls._redis_client
            url = (get_settings().REDIS_URL or "").strip()
            if not url:
                return None
            from redis import asyncio as redis_asyncio

            cls._redis_client = redis_asyncio.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            return cls._redis_client

    @staticmethod
    def _credits_key(tenant_id: str) -> str:
        return f"usage:credits:{tenant_id}"

    @staticmethod
    def _pending_key(tenant_id: str) -> str:
        return f"usage:pending_sync:{tenant_id}"

    @staticmethod
    def _last_sync_key(tenant_id: str) -> str:
        return f"usage:last_sync_ts:{tenant_id}"

    async def ensure_credit_bucket(self, *, tenant_id: str, plan: str) -> None:
        redis = await self._get_redis()
        if redis is None:
            return
        key = self._credits_key(tenant_id)
        exists = await redis.exists(key)
        if exists:
            return
        await redis.set(key, int(plan_initial_credits(plan)), nx=True)

    async def get_remaining_credits(self, *, tenant_id: str, plan: str) -> int:
        redis = await self._get_redis()
        if redis is None:
            return plan_initial_credits(plan)
        await self.ensure_credit_bucket(tenant_id=tenant_id, plan=plan)
        raw = await redis.get(self._credits_key(tenant_id))
        return max(0, int(raw or 0))

    async def check_credits(self, tenant_id: str, cost: int, *, plan: str = "starter") -> bool:
        remaining = await self.get_remaining_credits(tenant_id=tenant_id, plan=plan)
        return remaining >= max(1, int(cost))

    async def consume_credits(self, *, tenant_id: str, amount: int, plan: str = "starter") -> UsageResult:
        redis = await self._get_redis()
        n = max(1, int(amount))
        normalized_plan = normalize_plan(plan)
        if redis is None:
            return UsageResult(allowed=True, remaining_credits=plan_initial_credits(normalized_plan))

        await self.ensure_credit_bucket(tenant_id=tenant_id, plan=normalized_plan)
        allowed_raw, remaining_raw = await redis.eval(
            _USAGE_LUA,
            2,
            self._credits_key(tenant_id),
            self._pending_key(tenant_id),
            n,
        )
        allowed = bool(int(allowed_raw))
        remaining = max(0, int(remaining_raw or 0))
        if allowed:
            await self._maybe_alert_low_credit(
                tenant_id=tenant_id,
                plan=normalized_plan,
                remaining=remaining,
            )
            await self._maybe_sync_usage(tenant_id=tenant_id)
        return UsageResult(allowed=allowed, remaining_credits=remaining)

    async def _maybe_alert_low_credit(self, *, tenant_id: str, plan: str, remaining: int) -> None:
        initial_credits = max(1, int(plan_initial_credits(plan)))
        threshold = max(1, int(initial_credits * 0.10))
        if remaining >= threshold:
            return
        asyncio.create_task(
            send_alert(
                title="Credito bajo del tenant",
                message=(
                    "El saldo de creditos ha caido por debajo del 10% del plan y requiere "
                    "seguimiento para evitar bloqueo operativo."
                ),
                level="WARNING",
                context={
                    "tenant_id": tenant_id,
                    "plan": plan,
                    "remaining_credits": remaining,
                    "initial_credits": initial_credits,
                    "threshold_10pct": threshold,
                },
            )
        )

    async def _maybe_sync_usage(self, *, tenant_id: str) -> None:
        redis = await self._get_redis()
        if redis is None or self._db is None:
            return
        now = int(time.time())
        last_raw = await redis.get(self._last_sync_key(tenant_id))
        last = int(last_raw or 0)
        if now - last < 30:
            return
        await redis.set(self._last_sync_key(tenant_id), now, ex=300)
        await self.sync_to_postgres(tenant_id=tenant_id)

    async def sync_to_postgres(self, *, tenant_id: str) -> None:
        if self._db is None:
            return
        redis = await self._get_redis()
        if redis is None:
            return
        pending_key = self._pending_key(tenant_id)
        pending = int(await redis.get(pending_key) or 0)
        if pending <= 0:
            return
        try:
            await self._db.rpc(
                "record_tenant_credit_usage",
                {
                    "p_empresa_id": tenant_id,
                    "p_units": pending,
                    "p_type": "SYNC",
                    "p_description": "Periodic Redis bucket sync",
                },
            )
            await redis.decrby(pending_key, pending)
        except Exception as exc:
            _log.warning("usage_service: sync diferida no disponible: %s", exc)
