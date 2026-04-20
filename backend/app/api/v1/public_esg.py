"""Verificación pública de certificados ESG (QR / terceros). Usa service role solo en esta ruta acotada."""

from __future__ import annotations

from os import getenv

from fastapi import APIRouter, Depends, Query, Request

from app.api import deps
from app.core.http_client_meta import get_client_ip
from app.core.rate_limit import limiter
from app.db.supabase import SupabaseAsync
from app.schemas.esg_verify import EsgPublicVerifyOut
from app.services.esg_certificate_service import fetch_esg_verification_public

router = APIRouter(prefix="/v1/public")


def _esg_public_verify_rate_key(request: Request) -> str:
    """Anti-scraping: límite por IP (sin JWT en ruta pública)."""
    return f"esg_public_verify:{get_client_ip(request) or 'unknown'}"


# SlowAPI parsea el límite al importar el módulo: reiniciar workers tras cambiar env.
_ESG_PUBLIC_VERIFY_RATELIMIT = (getenv("ESG_PUBLIC_VERIFY_RATELIMIT") or "60/minute").strip() or "60/minute"


@router.get(
    "/verify-esg/{verification_code}",
    response_model=EsgPublicVerifyOut,
    summary="Verificar certificado ESG (hash PDF y datos de emisiones)",
)
@limiter.limit(_ESG_PUBLIC_VERIFY_RATELIMIT, key_func=_esg_public_verify_rate_key)
async def verify_esg_certificate(
    request: Request,
    verification_code: str,
    pdf_sha256: str | None = Query(
        None,
        description="SHA-256 hexadecimal del PDF recibido; si se envía, se indica si coincide con el registrado.",
    ),
    db: SupabaseAsync = Depends(deps.get_db_admin),
) -> EsgPublicVerifyOut:
    return await fetch_esg_verification_public(
        db,
        verification_code=verification_code,
        pdf_sha256=pdf_sha256,
    )
