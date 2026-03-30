"""Endpoints de salud: raíz (`/health`, `/ready`) y readiness profundo (`/health/deep`)."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(tags=["Salud"])


@router.get("/health", include_in_schema=True)
async def health() -> JSONResponse:
    """
    Salud operativa: conectividad **Supabase PostgREST** (datos).
    200 si la API de Supabase responde; 503 si no hay conexión.
    Para chequeo completo usar ``GET /health/deep``.
    """
    from app.core.health_checks import check_supabase_rest

    settings = get_settings()
    ok, detail = await check_supabase_rest(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    body = {
        "status": "ok" if ok else "degraded",
        "supabase": {"ok": ok, "detail": detail},
    }
    return JSONResponse(content=body, status_code=200 if ok else 503)


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
