"""Transparencia RGPD/SLA y divulgación coordinada de vulnerabilidades (RFC 9116)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings

router = APIRouter(tags=["Transparencia y cumplimiento"])

COMPLIANCE_VERSION = "1.0"
COMPLIANCE_LAST_REVIEW = "2026-04-19"

# Alineado con docs/legal/PRIVACY_POLICY.md y contratos de plataforma (actualizar ambos si cambia el stack).
SUBPROCESSORS: list[dict[str, Any]] = [
    {
        "category": "database_auth_storage",
        "description": "PostgreSQL, autenticación JWT, Row Level Security y almacenamiento gestionado.",
        "vendors": [{"name": "Supabase", "role": "Base de datos, Auth, Storage, Realtime (si se usa)"}],
    },
    {
        "category": "application_hosting",
        "description": "Ejecución de API, workers y red de aplicación.",
        "vendors": [{"name": "Railway", "role": "Contenedores backend / workers"}],
    },
    {
        "category": "frontend_cdn",
        "description": "Aplicación web y distribución en edge.",
        "vendors": [{"name": "Vercel", "role": "Frontend Next.js"}],
    },
    {
        "category": "maps_routing",
        "description": "Geocodificación, distancias y estimación de rutas cuando el cliente usa mapas.",
        "vendors": [{"name": "Google Maps Platform", "role": "APIs de mapas (clave servidor)"}],
    },
    {
        "category": "payments_banking",
        "description": "Cobro SaaS y agregación bancaria cuando el cliente las activa.",
        "vendors": [
            {"name": "Stripe", "role": "Pagos y facturación SaaS"},
            {"name": "GoCardless", "role": "Open Banking / Account Data y pagos"},
        ],
    },
    {
        "category": "ai_document_processing",
        "description": "Asistentes y OCR cuando el cliente usa funciones que llaman a proveedores externos.",
        "vendors": [
            {"name": "OpenAI", "role": "Modelos de lenguaje (LogisAdvisor, conciliación asistida, etc.)"},
            {"name": "Anthropic / Google / Azure", "role": "Proveedores alternativos según configuración"},
            {"name": "Microsoft Azure", "role": "Document Intelligence (OCR) si está configurado"},
        ],
    },
    {
        "category": "observability",
        "description": "Errores y rendimiento en producción.",
        "vendors": [{"name": "Sentry", "role": "APM y seguimiento de excepciones (sin PII por defecto en SDK)"}],
    },
    {
        "category": "email",
        "description": "Envío transaccional de correo.",
        "vendors": [{"name": "Resend", "role": "Email API (si está configurado)"}],
    },
]

SLA_SUMMARY: dict[str, Any] = {
    "legal_document_repo_path": "docs/legal/SLA.md",
    "uptime_target_monthly_percent": 99.9,
    "rpo_hours": 24,
    "rto_hours": 12,
    "support_response_hours": {
        "critical": 4,
        "high": 12,
        "normal": 48,
    },
    "maintenance_window_cet": "Sundays 02:00–05:00 (salvo acuerdo escrito)",
}

RGPD_PACK: dict[str, Any] = {
    "role": "Processor under GDPR (Encargado); Customer is Controller (Responsable).",
    "legal_documents_repo_paths": {
        "privacy_policy": "docs/legal/PRIVACY_POLICY.md",
        "dpa": "docs/legal/DPA_DATA_PROCESSING_AGREEMENT.md",
        "terms": "docs/legal/TERMS_OF_SERVICE.md",
    },
    "technical_measures_summary": [
        "Row Level Security (RLS) por tenant en Postgres/Supabase.",
        "Application-layer encryption for sensitive tokens (Fernet / multi-key rotation).",
        "Centralized secret retrieval via SecretManagerService (env, Vault KV v2, AWS Secrets Manager).",
        "HTTP security headers; rate limiting on auth and sensitive routes.",
        "Structured access logs with X-Request-ID correlation.",
    ],
    "right_to_erasure": {
        "description": "Admin API anonymizes user PII and revokes sessions; fiscal records may remain under legal hold.",
        "method": "POST",
        "path_template": "/api/v1/admin/compliance/anonymize/{user_id}",
        "auth": "Company administrator JWT",
    },
}

# Buzón canónico para divulgación coordinada (debe existir en DNS/MX y estar monitorizado en prod).
_DEFAULT_SECURITY_CONTACT = "security@ablogistics-os.com"

CYBER_POSTURE: dict[str, Any] = {
    "disclosure": {"rfc": "RFC 9116", "endpoint": "GET /.well-known/security.txt"},
    "healthchecks_for_sla_monitoring": {
        "liveness": "GET /live",
        "readiness": "GET /health",
        "deep_readiness": "GET /health/deep",
        "process": "GET /ready",
    },
    "incident_and_resilience_docs": [
        "docs/operations/DISASTER_RECOVERY.md",
        "docs/operations/health_recovery.md",
    ],
    "security_runbook": "README_SECURITY.md",
}


def _security_contact_mailto() -> str:
    settings = get_settings()
    raw = (settings.SECURITY_CONTACT_EMAIL or "").strip()
    if raw:
        return raw
    return _DEFAULT_SECURITY_CONTACT


@router.get("/api/v1/public/compliance", include_in_schema=True)
async def get_public_compliance_pack() -> dict[str, Any]:
    """
    Paquete de transparencia sin autenticación: subencargados, resumen SLA/RGPD y postura de seguridad.
    Las URLs legales canónicas para usuarios finales dependen del despliegue (landing/app); aquí se
    citan rutas de documentación en el repositorio como referencia estable para integradores y DD.
    """
    settings = get_settings()
    return {
        "product": settings.PROJECT_NAME,
        "compliance_pack_version": COMPLIANCE_VERSION,
        "last_review": COMPLIANCE_LAST_REVIEW,
        "environment_published": settings.ENVIRONMENT,
        "security_contact_email": _security_contact_mailto(),
        "gdpr": RGPD_PACK,
        "sla": SLA_SUMMARY,
        "subprocessors": SUBPROCESSORS,
        "cybersecurity": CYBER_POSTURE,
    }


@router.get("/.well-known/security.txt", include_in_schema=False)
async def get_security_txt() -> PlainTextResponse:
    """Divulgación coordinada de vulnerabilidades (RFC 9116)."""
    contact = _security_contact_mailto()
    expires_dt = datetime.now(timezone.utc) + timedelta(days=365)
    expires = expires_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    body = (
        f"Contact: mailto:{contact}\n"
        "Preferred-Languages: es, en\n"
        f"Expires: {expires}\n"
        "# Policy: see repository docs/legal/ and GET /api/v1/public/compliance\n"
    )
    return PlainTextResponse(content=body, media_type="text/plain; charset=utf-8")
