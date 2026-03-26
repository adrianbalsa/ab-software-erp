"""
Metadatos OpenAPI corporativos y personalización del esquema (seguridad JWT + HMAC webhooks).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

API_TITLE = "AB Logistics OS - API V1"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "API oficial para integraciones B2B, gestión de flota, emisiones ESG y tesorería automatizada.\n\n"
    "**Autenticación:** la mayoría de rutas requieren `Authorization: Bearer <JWT>` obtenido vía "
    "`POST /auth/login` (flujo OAuth2 password documentado en esta especificación).\n\n"
    "**Webhooks salientes B2B:** los eventos hacia URLs de cliente se firman con HMAC-SHA256; "
    "validar la cabecera `X-Webhook-Signature` (y `X-AB-Signature` en pings de prueba) según la documentación del endpoint receptor."
)

OPENAPI_CONTACT: dict[str, str] = {
    "name": "Soporte Técnico AB",
    "email": "api@ablogistics.com",
}

# Nombres exactos usados en include_router(..., tags=[...]) y en openapi_tags de FastAPI()
OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "Autenticación", "description": "Login, refresh de tokens JWT y contexto multi-tenant (RLS)."},
    {"name": "VeriFactu", "description": "Inalterabilidad fiscal, cadena de hash y comprobaciones AEAT."},
    {"name": "Facturas", "description": "Emisión, PDF, rectificativas y API versionada."},
    {"name": "Portes", "description": "Transporte, CMR, firma de entrega y documentación operativa."},
    {"name": "Flota", "description": "Vehículos, telemetría GPS, mantenimiento y alertas administrativas."},
    {"name": "Finanzas", "description": "Agregados financieros, cash-flow y servicios de tesorería ligados."},
    {"name": "Dashboard económico", "description": "Math Engine: KPIs, márgenes e insights económicos avanzados."},
    {"name": "Tesorería", "description": "Liquidez, vencimientos y proyección de caja."},
    {"name": "Bancos y conciliación", "description": "Movimientos bancarios, conciliación asistida e importaciones."},
    {"name": "Exportación", "description": "Exportación contable (CSV/Excel) para gestoría."},
    {"name": "ESG", "description": "Emisiones, informes de sostenibilidad e indicadores operativos."},
    {"name": "ESG - Auditoría", "description": "Auditoría de combustible, importaciones y reporting anual detallado."},
    {"name": "Pagos", "description": "Stripe Billing, checkout y webhooks de facturación SaaS."},
    {"name": "Webhooks B2B", "description": "Suscripciones HTTPS salientes, secretos HMAC y pruebas de entrega."},
    {"name": "IA y chat", "description": "LogisAdvisor y asistentes con contexto financiero/ESG."},
    {"name": "Mapas", "description": "Distancias, rutas y caché geográfico para operaciones."},
    {"name": "Clientes", "description": "Maestro de clientes y datos comerciales (RLS por empresa)."},
    {"name": "Portal cliente", "description": "Autoservicio B2B: entregas (POD) y facturas del cargador (rol CLIENTE)."},
    {"name": "Gastos", "description": "Gastos operativos, importación de combustible y categorización."},
    {"name": "Presupuestos", "description": "Presupuestos y cotizaciones comerciales."},
    {"name": "Empresa", "description": "Configuración de tenant, planes y datos de empresa."},
    {"name": "Facturación", "description": "Flujos de facturación internos y series."},
    {"name": "Dashboard", "description": "Panel operativo y métricas resumidas."},
    {"name": "Informes", "description": "Reporting descargable y agregados."},
    {"name": "Administración", "description": "Operaciones de administrador de plataforma y soporte."},
    {"name": "Auditoría API", "description": "Registro append-only de acciones para trazabilidad y cumplimiento."},
    {"name": "Eco", "description": "Métricas ecológicas y huella operativa."},
    {"name": "Salud", "description": "Healthchecks liveness/readiness y diagnóstico de infraestructura."},
]


def attach_custom_openapi(app: FastAPI) -> None:
    """Enriquece el esquema generado: contacto, esquemas de seguridad explícitos (JWT + HMAC)."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
            tags=getattr(app, "openapi_tags", None),
            contact=OPENAPI_CONTACT,
        )

        components = openapi_schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})

        # Documentación explícita: JWT Bearer (alineado con OAuth2 password de /auth/login)
        schemes["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Token de acceso JWT (Supabase Auth o emisión propia tras `POST /auth/login`). "
                "Enviar como `Authorization: Bearer <token>`."
            ),
        }

        # Webhooks salientes: el integrador valida el cuerpo con HMAC (no aplica a llamadas entrantes a esta API REST)
        schemes["WebhookHMAC"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-Webhook-Signature",
            "description": (
                "Firma HMAC-SHA256 del cuerpo JSON en entregas **salientes** hacia la URL suscrita. "
                "En entornos de prueba también se usa `X-AB-Signature`. "
                "No sustituye al JWT de la API REST; documenta el contrato B2B para receptores de eventos."
            ),
        }

        # Refuerzo de la descripción del esquema OAuth2 que genera FastAPI desde OAuth2PasswordBearer
        oauth2 = schemes.get("OAuth2PasswordBearer")
        if isinstance(oauth2, dict):
            oauth2["description"] = (
                "OAuth2 password flow contra `POST /auth/login`. La respuesta incluye `access_token` "
                "(JWT) para `Authorization: Bearer` en el resto de la API."
            )

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
