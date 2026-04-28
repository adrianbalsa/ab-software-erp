"""Rate limiting especializado:
- auth login/refresh por IP
- buckets costosos (AI/Maps/OCR) por tenant/usuario/IP
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

import anyio
from limits import parse
from redis import asyncio as redis_asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.http_client_meta import get_client_ip
from app.core.plans import PLAN_FREE, normalize_plan, plan_requests_per_minute
from app.core.rate_limit import (
    AUTH_RATE_LIMIT_PATHS,
    expensive_endpoint_bucket,
    get_rate_limit_strategy,
    is_rate_limit_exempt_path,
    rate_limit_key,
    rate_limit_response,
    resolve_rate_limit_identity,
)
from app.core.security import decode_access_token_payload
from app.services.usage_service import UsageService

_log = logging.getLogger(__name__)

_limit_auth = parse("10 per minute")


def _retry_after_seconds(strategy, limit_item, key: str) -> int:
    try:
        ws = strategy.get_window_stats(limit_item, key)
        rt = float(getattr(ws, "reset_time", 0))
        if rt:
            return max(1, int(rt - time.time()))
    except Exception:
        pass
    return 60


def _parse_limit_or_default(raw: str, fallback: str = "200 per minute"):
    try:
        return parse((raw or fallback).strip())
    except Exception:
        _log.warning("rate_limit: límite inválido %r; usando %s", raw, fallback)
        return parse(fallback)


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Límite HTTP global configurable por empresa.

    ``TENANT_RATE_LIMIT_DEFAULT`` cubre todos los tenants y
    ``TENANT_RATE_LIMIT_OVERRIDES`` permite límites por ``empresa_id``.
    """

    _redis_client = None
    _memory_windows: dict[str, list[float]] = {}

    async def _redis(self):
        if self._redis_client is not None:
            return self._redis_client
        settings = get_settings()
        url = (settings.REDIS_URL or "").strip()
        if not url:
            return None
        self._redis_client = redis_asyncio.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        return self._redis_client

    @staticmethod
    def _tenant_plan_from_request(request: Request, tenant_id: str) -> str:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return PLAN_FREE
        token = auth[7:].strip()
        if not token:
            return PLAN_FREE
        try:
            payload = decode_access_token_payload(token)
        except Exception:
            return PLAN_FREE
        claim_plan = (
            payload.get("plan")
            or payload.get("plan_type")
            or payload.get("app_role")
            or payload.get("user_role")
        )
        return normalize_plan(str(claim_plan or PLAN_FREE))

    async def _hit_tenant_sliding_window(self, *, tenant_id: str, rpm: int) -> tuple[bool, int]:
        def _memory_fallback() -> tuple[bool, int]:
            now = time.time()
            window_start = now - 60.0
            key = f"{tenant_id}:sliding"
            bucket = [ts for ts in self._memory_windows.get(key, []) if ts > window_start]
            bucket.append(now)
            self._memory_windows[key] = bucket
            if len(bucket) <= max(1, int(rpm)):
                return True, 0
            oldest = min(bucket)
            return False, max(1, int((oldest + 60.0) - now))
        redis = await self._redis()
        if redis is None:
            return _memory_fallback()
        now = time.time()
        window_start = now - 60.0
        key = f"rl:tenant:{tenant_id}:sliding"
        member = f"{int(time.time_ns())}-{uuid4().hex}"
        try:
            pipeline = redis.pipeline(transaction=True)
            pipeline.zremrangebyscore(key, "-inf", window_start)
            pipeline.zadd(key, {member: now})
            pipeline.zcard(key)
            pipeline.expire(key, 120)
            _, _, current, _ = await pipeline.execute()
            if current <= max(1, int(rpm)):
                return True, 0
            oldest_with_score = await redis.zrange(key, 0, 0, withscores=True)
            if not oldest_with_score:
                return False, 1
            oldest_score = float(oldest_with_score[0][1])
            retry_after = max(1, int((oldest_score + 60.0) - now))
            return False, retry_after
        except Exception:
            return _memory_fallback()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        if path in AUTH_RATE_LIMIT_PATHS or is_rate_limit_exempt_path(path):
            return await call_next(request)

        settings = get_settings()
        identity = resolve_rate_limit_identity(request)
        if not identity.tenant_id:
            return await call_next(request)
        tenant_id = str(identity.tenant_id).strip()
        plan = self._tenant_plan_from_request(request, tenant_id)
        rpm = plan_requests_per_minute(plan)
        override = settings.TENANT_RATE_LIMIT_OVERRIDES.get(tenant_id.lower())
        if override:
            limit_item = _parse_limit_or_default(override)
            rpm = int(getattr(limit_item, "amount", rpm))

        try:
            ok, retry_after = await self._hit_tenant_sliding_window(tenant_id=tenant_id, rpm=rpm)
        except Exception as exc:
            _log.warning("rate_limit tenant redis: error comprobando límite (dejamos pasar): %s", exc)
            return await call_next(request)

        if not ok:
            _log.warning(
                "rate_limit tenant exceeded scope=%s tenant_id=%s plan=%s rpm=%s",
                identity.scope,
                tenant_id,
                plan,
                rpm,
            )
            return rate_limit_response(
                request,
                retry_after_sec=retry_after,
                scope=identity.scope,
                tenant_id=tenant_id,
                limit=f"{rpm} per minute",
            )

        bucket = expensive_endpoint_bucket(path, request.method)
        if bucket in {"maps", "ai", "ocr"}:
            usage = UsageService()
            costs = {"maps": 5, "ai": 20, "ocr": 10}
            has_credits = await usage.check_credits(
                tenant_id=tenant_id,
                cost=costs[bucket],
                plan=plan,
            )
            if not has_credits:
                return Response(
                    status_code=429,
                    media_type="application/json",
                    content=(
                        '{"detail":"Créditos insuficientes para esta operación. '
                        'Recarga saldo o sube de plan para continuar."}'
                    ),
                )

        return await call_next(request)


class AuthLoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Solo rutas de autenticación; el resto lo cubre SlowAPI (200/min por clave)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        if path not in AUTH_RATE_LIMIT_PATHS:
            return await call_next(request)

        strategy = get_rate_limit_strategy()
        ip = get_client_ip(request) or "unknown"
        key = f"rl:auth:ip:{ip}"

        def _hit() -> bool:
            return strategy.hit(_limit_auth, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit auth: error comprobando límite (dejamos pasar): %s", exc)
            return await call_next(request)

        if not ok:
            ra = _retry_after_seconds(strategy, _limit_auth, key)
            _log.warning(
                "rate_limit auth exceeded key=%s scope=ip limit=%s",
                key,
                str(_limit_auth),
            )
            return rate_limit_response(
                request,
                retry_after_sec=ra,
                scope="ip",
                limit=str(_limit_auth),
            )

        return await call_next(request)


class EndpointCostRateLimitMiddleware(BaseHTTPMiddleware):
    """Cuotas específicas para endpoints de coste alto (AI, Maps, OCR)."""

    @staticmethod
    def _limit_item_for_bucket(bucket: str):
        s = get_settings()
        if bucket == "ai":
            return _parse_limit_or_default(s.AI_RATE_LIMIT, "30 per minute")
        if bucket == "maps":
            return _parse_limit_or_default(s.MAPS_RATE_LIMIT, "120 per minute")
        return _parse_limit_or_default(s.OCR_RATE_LIMIT, "20 per minute")

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.scope.get("path") or ""
        bucket = expensive_endpoint_bucket(path, request.method)
        if bucket is None:
            return await call_next(request)

        strategy = get_rate_limit_strategy()
        base_key = rate_limit_key(request)
        key = f"{base_key}:bucket:{bucket}"
        limit_item = self._limit_item_for_bucket(bucket)

        def _hit() -> bool:
            return strategy.hit(limit_item, key)

        try:
            ok = await anyio.to_thread.run_sync(_hit)
        except Exception as exc:
            _log.warning("rate_limit %s: error comprobando límite (dejamos pasar): %s", bucket, exc)
            return await call_next(request)

        if not ok:
            ra = _retry_after_seconds(strategy, limit_item, key)
            identity = resolve_rate_limit_identity(request)
            _log.warning(
                "rate_limit bucket exceeded key=%s bucket=%s scope=%s tenant_id=%s limit=%s",
                key,
                bucket,
                identity.scope,
                identity.tenant_id or "-",
                str(limit_item),
            )
            return rate_limit_response(
                request,
                retry_after_sec=ra,
                scope=identity.scope,
                tenant_id=identity.tenant_id,
                bucket=bucket,
                limit=str(limit_item),
            )

        return await call_next(request)
