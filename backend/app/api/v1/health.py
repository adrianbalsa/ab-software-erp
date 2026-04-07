"""Endpoints de salud: liveness ``GET /health`` (middleware), ``/ready``, readiness profundo ``/health/deep``."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(tags=["Salud"])


# GET /health (text/plain "OK") lo sirve ``HealthCheckBypassMiddleware`` en ``main.py`` (antes de TrustedHost).


@router.get("/health/deep", include_in_schema=True)
async def health_deep() -> JSONResponse:
    """
    Readiness profundo: Supabase REST, ``FinanceService``, Postgres (``DATABASE_URL``),
    Redis (``REDIS_URL`` opcional), listener TCP de PgBouncer. Para liveness usar ``GET /ready``.
    """
    from app.core import health_checks
    from app.db.supabase import get_supabase

    settings = get_settings()
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    body = await health_checks.run_deep_health(
        supabase_url=settings.SUPABASE_URL,
        service_key=settings.SUPABASE_SERVICE_KEY,
        db=db,
    )
    code = 200 if body.get("status") == "healthy" else 503
    return JSONResponse(content=body, status_code=code)


@router.get("/ready", include_in_schema=True)
async def ready() -> dict[str, str]:
    """Liveness rápido (proceso arriba). Healthchecks de Docker/K8s / Railway suelen usar este endpoint."""
    return {"status": "ready"}
