from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import admin, ai, auth, bank, bancos, clientes, dashboard, eco, empresa, esg, facturas, facturacion, finance, flota, gastos, maps, payments, portes, presupuestos, reports, utils
from app.core.config import get_settings
from app.db.supabase import get_supabase
from app.middleware.json_access_log import JsonAccessLogMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.slow_request_log import SlowRequestLogMiddleware


def create_app() -> FastAPI:
    from app.core.logging_config import configure_app_logging

    configure_app_logging()
    settings = get_settings()

    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(transaction_style="endpoint"),
            ],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE") or "0.1"),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE") or "0.0"),
        )

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Orden: primero añadido = más interno. El último = más externo (primero en ejecutarse en la petición).
    # SessionMiddleware (externo): cookies de sesión para el state OAuth (CSRF) entre redirecciones.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        session_cookie="abl_session",
        same_site="lax",
        https_only=settings.COOKIE_SECURE,
    )
    app.add_middleware(JsonAccessLogMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.ENVIRONMENT == "production",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(settings.CORS_ALLOW_ORIGINS),
        allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Más externo: mide duración total (incluye middleware interior) para umbral > 5 s.
    app.add_middleware(SlowRequestLogMiddleware)

    @app.get("/health", tags=["health"])
    async def health() -> JSONResponse:
        """
        Readiness profundo: Supabase REST, ``FinanceService``, Postgres (``DATABASE_URL``),
        Redis (``REDIS_URL`` opcional), listener TCP de PgBouncer (puerto 6432 o
        ``PGBOUNCER_HEALTH_HOST``). Para solo proceso vivo usar ``GET /ready``.
        """
        from app.core import health_checks

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

    @app.get("/ready", tags=["health"])
    async def ready() -> dict[str, str]:
        """Liveness rápido (proceso arriba). Healthchecks de Docker/K8s suelen usar este endpoint."""
        return {"status": "ready"}

    app.include_router(utils.router)
    app.include_router(payments.router, prefix="/payments", tags=["payments"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(portes.router, prefix="/portes", tags=["portes"])
    app.include_router(clientes.router, prefix="/clientes", tags=["clientes"])
    app.include_router(facturas.router, prefix="/facturas", tags=["facturas"])
    app.include_router(facturacion.router, prefix="/facturacion", tags=["facturacion"])
    app.include_router(gastos.router, prefix="/gastos", tags=["gastos"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
    app.include_router(empresa.router, prefix="/empresa", tags=["empresa"])
    app.include_router(finance.router, prefix="/finance", tags=["finance"])
    app.include_router(ai.router, prefix="/ai", tags=["ai"])
    app.include_router(maps.router, prefix="/maps", tags=["maps"])
    app.include_router(bancos.router, prefix="/bancos", tags=["bancos"])
    app.include_router(bank.router, prefix="/bank", tags=["bank"])
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(presupuestos.router, prefix="/presupuestos", tags=["presupuestos"])
    app.include_router(eco.router, prefix="/eco", tags=["eco"])
    app.include_router(esg.router, prefix="/esg", tags=["esg"])
    app.include_router(flota.router, prefix="/flota", tags=["flota"])

    return app


app = create_app()
