"""
Metadatos OpenAPI corporativos y personalización del esquema (seguridad JWT + HMAC webhooks).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

API_TITLE = "AB Logistics OS API"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "API oficial de AB Logistics OS para la gestión integral de transporte y logística.\n\n"
    "**Contrato estable para integradores:** usar rutas bajo **`/api/v1/`** para nuevas "
    "integraciones (móvil, B2B, partners). Las rutas sin prefijo existen por compatibilidad con "
    "el frontend actual; su estabilidad no está garantizada para clientes externos. "
    "Detalle: `docs/PLATFORM_CONTRACTS.md`.\n\n"
    "**Características Principales:**\n"
    "- **Cumplimiento Fiscal (VeriFactu):** Emisión de facturas con inalterabilidad, huella digital (cadena de hash) y envío a la AEAT.\n"
    "- **Motor ESG:** Cálculo automatizado de emisiones de CO2 y huella de carbono por ruta y vehículo.\n"
    "- **Gestión de Flota:** Telemetría GPS, mantenimientos y eficiencia de vehículos.\n"
    "- **Finanzas y Tesorería:** Analítica financiera en tiempo real, control de caja y conciliación bancaria.\n\n"
    "**Autenticación:** la mayoría de rutas requieren `Authorization: Bearer <JWT>` obtenido vía "
    "`POST /auth/login` (flujo OAuth2 password documentado en esta especificación).\n\n"
    "**Webhooks salientes B2B:** los eventos hacia URLs de cliente se firman con HMAC-SHA256; "
    "validar la cabecera `X-Webhook-Signature`."
)

OPENAPI_CONTACT: dict[str, str] = {
    "name": "Adrián Balsa - API Architect",
    "email": "api@ablogistics.com",
    "url": "https://ablogistics.com/api-docs",
}

OPENAPI_LICENSE: dict[str, str] = {
    "name": "Privada / Propietaria",
    "url": "https://ablogistics.com/legal",
}

# Nombres exactos usados en include_router(..., tags=[...]) y en openapi_tags de FastAPI()
OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "Finanzas", "description": "Agregados financieros, cash-flow, tesorería y analítica (Math Engine)."},
    {"name": "Flota", "description": "Gestión de vehículos, telemetría GPS, mantenimiento y eficiencia operativa."},
    {"name": "Onboarding", "description": "Autoservicio B2B, registro de clientes y aceptación de riesgos."},
    {"name": "Fiscal (AEAT)", "description": "Facturación electrónica, VeriFactu, inalterabilidad y envío a la AEAT."},
    {"name": "ESG", "description": "Cálculo de emisiones de CO2, informes de sostenibilidad e indicadores ambientales."},
    
    # Resto de tags para compatibilidad con el enrutamiento actual
    {"name": "Autenticación", "description": "Login, refresh de tokens JWT y contexto multi-tenant (RLS)."},
    {"name": "VeriFactu", "description": "Operaciones específicas de VeriFactu (remplazado gradualmente por Fiscal (AEAT))."},
    {"name": "Facturas", "description": "Emisión, PDF, rectificativas y API versionada."},
    {"name": "Portes", "description": "Transporte, CMR, firma de entrega y documentación operativa."},
    {"name": "Dashboard económico", "description": "Math Engine: KPIs, márgenes e insights económicos avanzados."},
    {"name": "Tesorería", "description": "Liquidez, vencimientos y proyección de caja."},
    {"name": "Banking", "description": "Open Banking (GoCardless), sincronización, conciliación fuzzy y asistida por IA."},
    {"name": "Bancos y conciliación", "description": "Movimientos bancarios, conciliación asistida e importaciones."},
    {"name": "Exportación", "description": "Exportación contable (CSV/Excel) para gestoría."},
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
    {
        "name": "Transparencia y cumplimiento",
        "description": "RGPD/SLA/postura de seguridad sin autenticación: JSON de transparencia y security.txt (RFC 9116).",
    },
    {"name": "Flota - Análisis", "description": "Analíticas avanzadas de flota."},
    {"name": "Webhooks externos", "description": "Webhooks de proveedores externos (GoCardless, Stripe)."},
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
            license_info=OPENAPI_LICENSE,
        )

        components = openapi_schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})

        # Documentación explícita: JWT Bearer (alineado con OAuth2 password de /auth/login)
        schemes["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Token de acceso JWT (Supabase Auth o emisión propia tras `POST /auth/login` / OAuth). "
                "Enviar como `Authorization: Bearer <token>` o cookie HttpOnly (`ACCESS_TOKEN_COOKIE_NAME`, "
                "por defecto `abl_auth_token`) en el mismo sitio que la API."
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

        oauth2 = schemes.get("OAuth2PasswordBearer")
        if isinstance(oauth2, dict):
            oauth2["description"] = (
                "OAuth2 password flow contra `POST /auth/login`. La respuesta incluye `access_token` "
                "(JWT) y cookies HttpOnly de acceso/refresh en el dominio de la API."
            )

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
