from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from typing import AsyncIterator
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette import status as starlette_status

from app.api.routes import (
    admin,
    ai,
    audit_logs,
    auth,
    clientes,
    dashboard,
    eco,
    empresa,
    esg,
    facturas,
    facturacion,
    finance,
    flota,
    gastos,
    maps,
    payments,
    portes,
    presupuestos,
    reports,
    utils,
)
from app.api.endpoints import ai as ai_endpoints
from app.api.v1 import auth as auth_password_v1
from app.api.v1 import advisor as advisor_v1
from app.api.v1 import bi as bi_v1
from app.api.v1 import product_config as product_config_v1
from app.api.v1 import analytics as analytics_v1
from app.api.v1 import banking as banking_v1
from app.api.v1 import ai_documents as ai_documents_v1
from app.api.v1 import chat as chat_v1
from app.api.v1 import chatbot as chatbot_v1
from app.api.v1 import clientes as clientes_v1
from app.api.v1 import economic_dashboard as economic_dashboard_v1
from app.api.v1 import esg as esg_v1
from app.api.v1 import esg_auditoria as esg_auditoria_v1
from app.api.v1 import esg_reports as esg_reports_v1
from app.api.v1 import export as export_v1
from app.api.v1 import facturas_pdf as facturas_pdf_v1
from app.api.v1 import finance_dashboard as finance_dashboard_v1
from app.api.v1 import fleet_analytics as fleet_analytics_v1
from app.api.v1 import flota_dashboard as flota_dashboard_v1
from app.api.v1 import flota_ubicacion as flota_ubicacion_v1
from app.api.v1 import gastos_combustible as gastos_combustible_v1
from app.api.v1 import health as health_router
from app.api.v1 import payments_gocardless as payments_gocardless_v1
from app.api.v1 import portal_cliente as portal_cliente_v1
from app.api.v1 import portal_onboarding as portal_onboarding_v1
from app.api.v1 import portes as portes_v1
from app.api.v1 import routes_optimizer as routes_optimizer_v1
from app.api.v1 import admin as admin_v1
from app.api.v1 import admin_esg as admin_esg_v1
from app.api.v1 import admin_compliance as admin_compliance_v1
from app.api.v1 import public_compliance as public_compliance_v1
from app.api.v1 import public_esg as public_esg_v1
from app.api.v1 import stripe
from app.api.v1.webhooks import stripe as stripe_webhook_v1
from app.api.v1.webhooks import esg_external_verify as webhooks_esg_external_v1
from app.api.v1 import treasury as treasury_v1
from app.api.v1 import verifactu as verifactu_v1
from app.api.v1.webhooks import b2b as webhooks_v1
from app.api.v1.webhooks import gocardless as webhooks_gocardless_v1
from app.core.config import ConfigError, Settings, get_settings
from app.core.job_queue import close_arq_redis_pool
from app.core.rate_limit import (
    SkipOptionsSlowAPIMiddleware,
    limiter,
    rate_limit_exceeded_handler,
    warmup_rate_limit_backend,
)
from app.middleware.health_bypass import HealthCheckBypassMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.login_debug_print import LoginDebugPrintMiddleware
from app.middleware.json_access_log import JsonAccessLogMiddleware
from app.middleware.audit_log_middleware import AuditLogMiddleware
from app.middleware.fiscal_rate_limit_middleware import FiscalVerifactuRateLimitMiddleware
from app.middleware.rate_limit_middleware import AuthLoginRateLimitMiddleware, EndpointCostRateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.slow_request_log import SlowRequestLogMiddleware
from app.middleware.tenant_rbac_context import TenantRBACContextMiddleware
from app.openapi_config import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    OPENAPI_TAGS,
    attach_custom_openapi,
)
from app.core.sentry_privacy import scrub_sentry_breadcrumb
from app.services.alert_service import alert_service, notify_critical_error, short_traceback_from_exc


def _sentry_traces_sample_rate(env: str) -> float:
    """1.0 en staging/desarrollo; 0.1 en production (override: ``SENTRY_TRACES_SAMPLE_RATE``)."""
    raw = (os.getenv("SENTRY_TRACES_SAMPLE_RATE") or "").strip()
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            pass
    return 0.1 if env == "production" else 1.0


def _sentry_profiles_sample_rate(env: str, traces: float) -> float:
    """Perfiles CPU (p. ej. Math Engine bajo transacciones muestreadas). Override: ``SENTRY_PROFILES_SAMPLE_RATE``."""
    raw = (os.getenv("SENTRY_PROFILES_SAMPLE_RATE") or "").strip()
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            pass
    return 0.1 if env == "production" else min(traces, 1.0)


def _init_sentry(settings: Settings) -> None:
    """Inicializa Sentry tras ``get_settings()`` (única fuente del DSN vía ``SENTRY_DSN``)."""
    dsn = (settings.SENTRY_DSN or "").strip()
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    env = str(getattr(settings, "ENVIRONMENT", "development")).strip().lower()
    traces = _sentry_traces_sample_rate(env)
    profiles = _sentry_profiles_sample_rate(env, traces)
    release = (
        (os.getenv("APP_RELEASE") or "").strip()
        or (os.getenv("RAILWAY_GIT_COMMIT_SHA") or "").strip()
        or (os.getenv("VERCEL_GIT_COMMIT_SHA") or "").strip()
        or None
    )

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=release,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        traces_sample_rate=traces,
        profiles_sample_rate=profiles,
        send_default_pii=False,
        max_request_body_size="never",
        before_breadcrumb=scrub_sentry_breadcrumb,
    )


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await warmup_rate_limit_backend()
    yield
    await close_arq_redis_pool()


def create_app() -> FastAPI:
    from app.core.logging_config import configure_app_logging

    configure_app_logging()
    settings = get_settings()
    _init_sentry(settings)
    # Defensa en profundidad: en producción ``get_settings()`` ya exige ``DATABASE_URL`` explícita.
    if settings.ENVIRONMENT == "production" and not (settings.DATABASE_URL or "").strip():
        raise ConfigError(
            "DATABASE_URL resuelta vacía en producción: se requiere Postgres directo para "
            "candados transaccionales VeriFactu y coherencia multi-réplica."
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
        lifespan=_lifespan,
    )
    attach_custom_openapi(app)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Orden: primero añadido = más interno. El último = más externo (primero en ejecutarse en la petición).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        session_cookie="abl_session",
        same_site="lax",
        https_only=settings.COOKIE_SECURE,
    )
    app.add_middleware(JsonAccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.ENVIRONMENT == "production",
    )
    origins = (
        [
            origin.strip()
            for origin in settings.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]
        if isinstance(settings.CORS_ALLOW_ORIGINS, str)
        else [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS if str(origin).strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SlowRequestLogMiddleware)
    app.add_middleware(SkipOptionsSlowAPIMiddleware)
    app.add_middleware(AuthLoginRateLimitMiddleware)
    app.add_middleware(EndpointCostRateLimitMiddleware)
    # Debe ejecutarse antes que el resto de middlewares de rate limit para envolver
    # envíos fiscales AEAT (ruta /api/v1/verifactu y finalizaciones de factura).
    app.add_middleware(FiscalVerifactuRateLimitMiddleware)
    # Lista explícita (sin "*"); GET /live (liveness) antes vía HealthCheckBypassMiddleware.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.ALLOWED_HOSTS),
    )
    # Más externo aún: print stderr antes de TrustedHost / OAuth2 body (depurar 401 sin entrar en la ruta).
    app.add_middleware(LoginDebugPrintMiddleware)
    # Contexto tenant/RBAC para reforzar RLS incluso si un endpoint olvida una dependencia.
    app.add_middleware(TenantRBACContextMiddleware)
    # Trazabilidad automática de escrituras API en public.audit_logs (no bloqueante).
    app.add_middleware(AuditLogMiddleware)
    # Debe ser el más externo: responde /health antes de TrustedHost y middlewares tenant/RBAC.
    app.add_middleware(HealthCheckBypassMiddleware)

    @app.exception_handler(RequestValidationError)
    async def request_validation_login_debug(request: Request, exc: RequestValidationError):
        """422 en login suele ser JSON en lugar de form-urlencoded (OAuth2PasswordRequestForm)."""
        if request.url.path.rstrip("/") == "/auth/login":
            print(
                "LOGIN 422 RequestValidationError (¿Content-Type application/json?). "
                f"errors={jsonable_encoder(exc.errors())}",
                flush=True,
            )
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        if exc.status_code == 500:
            asyncio.create_task(notify_critical_error(short_traceback_from_exc(exc)))
        detail: object = exc.detail
        if exc.status_code == starlette_status.HTTP_403_FORBIDDEN and (
            detail is None
            or detail == ""
            or (isinstance(detail, str) and not str(detail).strip())
        ):
            detail = "Not enough privileges"
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": jsonable_encoder(detail)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        asyncio.create_task(notify_critical_error(short_traceback_from_exc(exc)))
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    @app.get("/health", tags=["Salud"], include_in_schema=True)
    async def health(request: Request) -> JSONResponse:
        """
        Readiness con dependencias críticas (Supabase REST + Redis obligatorio).
        Liveness barato sin TrustedHost: ``GET /live``.
        """
        from app.core.health_checks import _check_dict, check_redis_ping, check_supabase_rest
        from app.db.supabase import get_supabase

        settings = get_settings()
        db = await get_supabase(
            jwt_token=None,
            allow_service_role_bypass=True,
            log_service_bypass_warning=False,
        )
        _ = db  # Garantiza creación del cliente admin en el propio healthcheck.

        supabase_ok, supabase_detail = await check_supabase_rest(
            settings_url=settings.SUPABASE_URL,
            service_key=settings.SUPABASE_SERVICE_KEY,
        )
        redis = await check_redis_ping()
        if redis.get("skipped"):
            redis = _check_dict(ok=False, detail="redis_not_configured", skipped=False)

        checks = {
            "supabase": _check_dict(ok=supabase_ok, detail=supabase_detail, skipped=False),
            "redis": redis,
        }
        healthy = all(bool(check.get("ok")) and not bool(check.get("skipped")) for check in checks.values())
        status_code = 200 if healthy else 503
        if status_code == 503:
            await alert_service.send_critical_alert(
                message="Healthcheck failed: one or more critical dependencies are down.",
                details={"endpoint": "/health", "status_code": status_code, "checks": checks},
            )
        payload: dict[str, object] = {
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks,
        }
        rid = getattr(request.state, "request_id", None)
        if rid:
            payload["request_id"] = rid
        return JSONResponse(status_code=status_code, content=payload)

    # Salud en la raíz (Railway healthcheck: GET /live; readiness: GET /health, GET /ready).
    app.include_router(health_router.router)
    app.include_router(public_compliance_v1.router)
    app.include_router(public_esg_v1.router, tags=["ESG — verificación pública"])
    app.include_router(utils.router, tags=["Salud"])
    app.include_router(payments.router, prefix="/payments", tags=["Pagos"])
    app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
    app.include_router(auth_password_v1.router, prefix="/api/v1/auth", tags=["Autenticación"])
    app.include_router(portes.router, prefix="/portes", tags=["Portes"])
    app.include_router(portes.router, prefix="/api/v1/portes", tags=["Portes"])
    app.include_router(clientes.router, prefix="/clientes", tags=["Clientes"])
    app.include_router(facturas.router, prefix="/facturas", tags=["Facturas"])
    # Mismo router que `/facturas` (evita duplicar import `app.api.v1.facturas`).
    app.include_router(facturas.router, prefix="/api/v1/facturas", tags=["Facturas"])
    app.include_router(facturas_pdf_v1.router, prefix="/api/v1/facturas", tags=["Facturas"])
    app.include_router(
        economic_dashboard_v1.router,
        prefix="/api/v1/dashboard",
        tags=["Dashboard económico"],
    )
    app.include_router(facturacion.router, prefix="/facturacion", tags=["Facturación"])
    app.include_router(gastos.router, prefix="/gastos", tags=["Gastos"])
    app.include_router(gastos.router, prefix="/api/v1/gastos", tags=["Gastos"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
    app.include_router(empresa.router, prefix="/empresa", tags=["Empresa"])
    app.include_router(finance.router, prefix="/finance", tags=["Finanzas"])
    app.include_router(ai.router, prefix="/ai", tags=["IA y chat"])
    app.include_router(ai_endpoints.router, prefix="/ai", tags=["IA y chat"])
    app.include_router(maps.router, prefix="/maps", tags=["Mapas"])
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
    app.include_router(
        stripe_webhook_v1.router,
        prefix="/api/v1",
        tags=["Webhooks Stripe"],
    )
    app.include_router(
        webhooks_esg_external_v1.router,
        prefix="/api/v1/webhooks",
        tags=["Webhooks ESG"],
    )
    app.include_router(
        admin_compliance_v1.router,
        prefix="/api/v1/admin",
        tags=["Administración — cumplimiento"],
    )
    app.include_router(
        admin_v1.router,
        prefix="/api/v1/admin",
        tags=["Administración"],
    )
    app.include_router(
        admin_esg_v1.router,
        prefix="/api/v1/admin",
        tags=["ESG — administración"],
    )
    app.include_router(payments_gocardless_v1.router, prefix="/api/v1/payments/gocardless", tags=["Pagos"])
    app.include_router(esg_reports_v1.router, prefix="/api/v1", tags=["ESG"])
    app.include_router(esg_v1.router, prefix="/api/v1", tags=["ESG"])
    app.include_router(esg_auditoria_v1.router, prefix="/api/v1", tags=["ESG - Auditoría"])
    app.include_router(chat_v1.router, prefix="/api/v1/chat", tags=["IA y chat"])
    app.include_router(
        ai_documents_v1.router,
        prefix="/api/v1/ai",
        tags=["IA — Vampire Radar / Economic Advisor"],
    )
    app.include_router(chatbot_v1.router, prefix="/api/v1/chatbot", tags=["IA y chat"])
    app.include_router(banking_v1.router, prefix="/api/v1/banking", tags=["Banking"])
    app.include_router(treasury_v1.router, prefix="/api/v1/treasury", tags=["Tesorería"])
    app.include_router(export_v1.router, prefix="/api/v1/export", tags=["Exportación"])
    app.include_router(portes_v1.router, prefix="/api/v1/portes", tags=["Portes"])
    app.include_router(clientes_v1.router, prefix="/api/v1/clientes", tags=["Clientes"])
    app.include_router(gastos_combustible_v1.router, prefix="/api/v1/gastos", tags=["Gastos"])
    app.include_router(finance_dashboard_v1.router, prefix="/api/v1/finance", tags=["Finanzas"])
    app.include_router(verifactu_v1.router, prefix="/api/v1/verifactu", tags=["Fiscal (AEAT)"])
    app.include_router(routes_optimizer_v1.router, prefix="/api/v1/routes", tags=["Optimización de rutas"])
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
    app.include_router(advisor_v1.router, prefix="/api/v1/advisor", tags=["LogisAdvisor"])
    app.include_router(bi_v1.router, prefix="/api/v1", tags=["Business Intelligence"])
    app.include_router(product_config_v1.router, prefix="/api/v1")

    return app


app = create_app()
