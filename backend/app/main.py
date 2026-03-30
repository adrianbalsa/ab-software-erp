from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import admin, ai, audit_logs, auth, bank, bancos, clientes, dashboard, eco, empresa, esg, facturas, facturacion, finance, flota, gastos, maps, payments, portes, presupuestos, reports, utils
from app.core.config import get_settings
from app.db.supabase import get_supabase
from app.middleware.json_access_log import JsonAccessLogMiddleware
from app.middleware.rate_limit_middleware import AuthLoginRateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.slow_request_log import SlowRequestLogMiddleware

# 1. Importamos tu nuevo router de Stripe junto a los demás
from app.api.v1 import bancos_conciliacion as bancos_conciliacion_v1
from app.api.v1 import export as export_v1
from app.api.v1 import portes as portes_v1
from app.api.v1 import treasury as treasury_v1
from app.api.v1 import chat as chat_v1
from app.api.v1 import economic_dashboard as economic_dashboard_v1
from app.api.v1 import clientes as clientes_v1
from app.api.v1 import esg_reports as esg_reports_v1
from app.api.v1 import esg_auditoria as esg_auditoria_v1
from app.api.v1 import facturas as facturas_v1
from app.api.v1 import facturas_pdf as facturas_pdf_v1
from app.api.v1 import finance_dashboard as finance_dashboard_v1
from app.api.v1 import flota_ubicacion as flota_ubicacion_v1
from app.api.v1 import flota_dashboard as flota_dashboard_v1
from app.api.v1 import fleet_analytics as fleet_analytics_v1
from app.api.v1 import payments_gocardless as payments_gocardless_v1
from app.api.v1 import stripe
from app.api.v1 import gastos_combustible as gastos_combustible_v1
from app.api.v1 import health as health_v1
from app.api.v1 import verifactu as verifactu_v1
from app.api.v1 import webhooks as webhooks_v1
from app.api.v1 import webhooks_gocardless as webhooks_gocardless_v1
from app.api.v1 import portal_cliente as portal_cliente_v1
from app.api.v1 import portal_onboarding as portal_onboarding_v1
from app.api.v1 import analytics as analytics_v1

from app.core.alerts import short_traceback_from_exc, schedule_critical_error_alert
from app.core.rate_limit import SkipOptionsSlowAPIMiddleware, limiter
from app.openapi_config import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    OPENAPI_TAGS,
    attach_custom_openapi,
)


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
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"displayRequestDuration": True, "syntaxHighlight.theme": "monokai"},
        debug=settings.DEBUG,
    )
    attach_custom_openapi(app)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    # Rate limit por IP (SlowAPI 100/min); login/refresh exentos y 5/min por IP aquí.
    app.add_middleware(SkipOptionsSlowAPIMiddleware)
    app.add_middleware(AuthLoginRateLimitMiddleware)
    # Primera línea de defensa: Host permitido (API detrás de proxy con --proxy-headers).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.ALLOWED_HOSTS))

    @app.get("/health", tags=["Salud"])
    async def health() -> JSONResponse:
        """
        Salud operativa del búnker: conectividad **Supabase PostgREST** (datos).
        200 si la API de Supabase responde; 503 si no hay conexión.
        Para chequeo completo (Postgres directo, Redis, PgBouncer) usar ``GET /health/deep``.
        """
        from app.core.health_checks import check_supabase_rest

        ok, detail = await check_supabase_rest(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        body = {
            "status": "ok" if ok else "degraded",
            "supabase": {"ok": ok, "detail": detail},
        }
        return JSONResponse(content=body, status_code=200 if ok else 503)

    @app.get("/health/deep", tags=["Salud"])
    async def health_deep() -> JSONResponse:
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

    @app.get("/ready", tags=["Salud"])
    async def ready() -> dict[str, str]:
        """Liveness rápido (proceso arriba). Healthchecks de Docker/K8s suelen usar este endpoint."""
        return {"status": "ready"}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # Captura 500 explícitos (si los hubiera) y dispara alerta crítica.
        if exc.status_code == 500:
            schedule_critical_error_alert(
                request=request,
                error_detail=short_traceback_from_exc(exc),
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Captura cualquier 500 no controlado.
        schedule_critical_error_alert(
            request=request,
            error_detail=short_traceback_from_exc(exc),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    app.include_router(utils.router, tags=["Salud"])
    app.include_router(payments.router, prefix="/payments", tags=["Pagos"])
    app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
    app.include_router(portes.router, prefix="/portes", tags=["Portes"])
    # Alias versionado (misma semántica que `/portes/*` para clientes BFF / integraciones).
    app.include_router(portes.router, prefix="/api/v1/portes", tags=["Portes"])
    app.include_router(clientes.router, prefix="/clientes", tags=["Clientes"])
    app.include_router(facturas.router, prefix="/facturas", tags=["Facturas"])
    app.include_router(facturas_v1.router, prefix="/api/v1/facturas", tags=["Facturas"])
    app.include_router(facturas_pdf_v1.router, prefix="/api/v1/facturas", tags=["Facturas"])
    app.include_router(
        economic_dashboard_v1.router,
        prefix="/api/v1/dashboard",
        tags=["Dashboard económico"],
    )
    app.include_router(facturacion.router, prefix="/facturacion", tags=["Facturación"])
    app.include_router(gastos.router, prefix="/gastos", tags=["Gastos"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
    app.include_router(empresa.router, prefix="/empresa", tags=["Empresa"])
    app.include_router(finance.router, prefix="/finance", tags=["Finanzas"])
    app.include_router(ai.router, prefix="/ai", tags=["IA y chat"])
    app.include_router(maps.router, prefix="/maps", tags=["Mapas"])
    app.include_router(bancos.router, prefix="/bancos", tags=["Bancos y conciliación"])
    app.include_router(bank.router, prefix="/bank", tags=["Bancos y conciliación"])
    app.include_router(reports.router, prefix="/reports", tags=["Informes"])
    app.include_router(admin.router, prefix="/admin", tags=["Administración"])
    app.include_router(presupuestos.router, prefix="/presupuestos", tags=["Presupuestos"])
    app.include_router(eco.router, prefix="/eco", tags=["Eco"])
    app.include_router(esg.router, prefix="/esg", tags=["ESG"])
    app.include_router(flota.router, prefix="/flota", tags=["Flota"])
    app.include_router(flota_ubicacion_v1.router, prefix="/api/v1/flota", tags=["Flota"])
    app.include_router(flota_dashboard_v1.router, prefix="/api/v1/flota", tags=["Flota"])
    app.include_router(fleet_analytics_v1.router, prefix="/api/v1/fleet", tags=["Flota - Análisis"])

    app.include_router(stripe.router, prefix="/api/v1/stripe", tags=["Pagos"])
    app.include_router(payments_gocardless_v1.router, prefix="/api/v1/payments/gocardless", tags=["Pagos"])
    app.include_router(esg_reports_v1.router, prefix="/api/v1", tags=["ESG"])
    app.include_router(esg_auditoria_v1.router, prefix="/api/v1", tags=["ESG - Auditoría"])
    app.include_router(chat_v1.router, prefix="/api/v1/chat", tags=["IA y chat"])
    app.include_router(bancos_conciliacion_v1.router, prefix="/api/v1/bancos", tags=["Bancos y conciliación"])
    app.include_router(treasury_v1.router, prefix="/api/v1/treasury", tags=["Tesorería"])
    app.include_router(export_v1.router, prefix="/api/v1/export", tags=["Exportación"])
    app.include_router(portes_v1.router, prefix="/api/v1/portes", tags=["Portes"])
    app.include_router(clientes_v1.router, prefix="/api/v1/clientes", tags=["Clientes"])
    app.include_router(gastos_combustible_v1.router, prefix="/api/v1/gastos", tags=["Gastos"])
    app.include_router(finance_dashboard_v1.router, prefix="/api/v1/finance", tags=["Finanzas"])
    app.include_router(health_v1.router, prefix="/api/v1", tags=["Salud"])
    app.include_router(verifactu_v1.router, prefix="/api/v1/verifactu", tags=["Fiscal (AEAT)"])
    app.include_router(audit_logs.router, prefix="/api/v1/audit-logs", tags=["Auditoría API"])
    app.include_router(webhooks_v1.router, prefix="/api/v1/webhooks", tags=["Webhooks B2B"])
    app.include_router(
        webhooks_gocardless_v1.router,
        prefix="/api/v1/webhooks",
        tags=["Webhooks externos"],
    )
    app.include_router(
        portal_cliente_v1.router,
        prefix="/api/v1/portal",
        tags=["Portal cliente"],
    )
    app.include_router(
        portal_onboarding_v1.router,
        prefix="/api/v1/portal",
        tags=["Onboarding"],
    )
    app.include_router(analytics_v1.router, prefix="/api/v1", tags=["Finanzas"])

    return app


app = create_app()