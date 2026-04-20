"""ZIP de evidencias Due Diligence / auditores (sin datos operativos ni PII de clientes)."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from app.api.v1.public_compliance import build_public_compliance_pack, build_security_txt_body
from app.core.plans import (
    EUR_MONTHLY_COMPLIANCE,
    EUR_MONTHLY_FINANCE,
    EUR_MONTHLY_FULL_STACK,
    PLAN_ENTERPRISE,
    PLAN_PRO,
    PLAN_STARTER,
    billing_addons,
    plan_marketing_name,
)


def _pricing_catalog() -> dict[str, Any]:
    return {
        "currency": "EUR",
        "billing_period": "monthly",
        "notes": "Montos orientativos de catálogo (IVA aparte). Los cargos efectivos los define Stripe (Price IDs vía STRIPE_PRICE_* en despliegue).",
        "base_plans": [
            {
                "plan_slug": PLAN_STARTER,
                "marketing_name": plan_marketing_name(PLAN_STARTER),
                "eur_monthly": EUR_MONTHLY_COMPLIANCE,
            },
            {
                "plan_slug": PLAN_PRO,
                "marketing_name": plan_marketing_name(PLAN_PRO),
                "eur_monthly": EUR_MONTHLY_FINANCE,
            },
            {
                "plan_slug": PLAN_ENTERPRISE,
                "marketing_name": plan_marketing_name(PLAN_ENTERPRISE),
                "eur_monthly": EUR_MONTHLY_FULL_STACK,
            },
        ],
        "addons": [asdict(a) for a in billing_addons()],
    }


def _index_readme(*, generated_at_iso: str) -> str:
    return f"""# AB Logistics OS — paquete de evidencias (Due Diligence / auditores)

**Generado (UTC):** {generated_at_iso}

## Contenido de este ZIP

| Archivo | Descripción |
|---------|-------------|
| `public_compliance_snapshot.json` | Misma información que `GET /api/v1/public/compliance` (subencargados, RGPD, SLA, postura ciber). **Sin** datos operativos de transporte. |
| `pricing_catalog.json` | Matriz comercial de referencia (planes base + add-ons); alinear con Stripe Dashboard y `docs/operations/STRIPE_BILLING.md`. |
| `security.txt` | Copia del cuerpo publicado en `GET /.well-known/security.txt` (RFC 9116). |

## Documentación en repositorio (no incluida en el ZIP)

- `docs/legal/COMPLIANCE_AND_SECURITY_POSTURE.md`
- `docs/PLATFORM_CONTRACTS.md`
- `README_SECURITY.md`
- `docs/operations/STRIPE_BILLING.md` / `docs/operations/DISASTER_RECOVERY.md`

## Limitación

Este paquete **no** sustituye a un Data Room legal ni a exportaciones fiscales/ESG con alcance normativo propio; agrega evidencias de **postura de plataforma** y **catálogo comercial** para compradores y auditores externos.
""".strip()


def build_audit_package_zip_bytes() -> bytes:
    """Construye el ZIP en memoria."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    buf = io.BytesIO()
    snapshot = {
        **build_public_compliance_pack(),
        "audit_package_generated_at_utc": generated_at,
    }
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("INDEX.md", _index_readme(generated_at_iso=generated_at))
        zf.writestr(
            "public_compliance_snapshot.json",
            json.dumps(snapshot, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "pricing_catalog.json",
            json.dumps(_pricing_catalog(), ensure_ascii=False, indent=2),
        )
        zf.writestr("security.txt", build_security_txt_body())
    return buf.getvalue()
