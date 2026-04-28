from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.core.plans import PLAN_FREE, normalize_plan
from app.core.rate_limit import resolve_rate_limit_identity
from app.services.usage_service import UsageService


def _resolve_context(kwargs: dict[str, Any]) -> tuple[str, str]:
    current_user = kwargs.get("current_user")
    if current_user is not None and getattr(current_user, "empresa_id", None):
        tenant_id = str(current_user.empresa_id)
        plan = normalize_plan(getattr(current_user, "plan_type", None) or PLAN_FREE)
        return tenant_id, plan

    request = kwargs.get("request")
    if isinstance(request, Request):
        identity = resolve_rate_limit_identity(request)
        tenant_id = str(identity.tenant_id or "").strip()
        if tenant_id:
            return tenant_id, PLAN_FREE
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo resolver tenant para control de créditos",
    )


def consume_credits(amount: int) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    Decorador para endpoints caros: consume créditos de forma atómica en Redis.
    """

    def _decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def _wrapper(*args: Any, **kwargs: Any) -> Any:
            tenant_id, plan = _resolve_context(kwargs)
            db = kwargs.get("db")
            service = UsageService(db=db)
            result = await service.consume_credits(
                tenant_id=tenant_id,
                amount=max(1, int(amount)),
                plan=plan,
            )
            if not result.allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Créditos insuficientes para esta operación. "
                        "Recarga saldo o sube de plan para continuar."
                    ),
                )
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator
