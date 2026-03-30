"""Healthcheck operativo para SRE (Supabase + estado del búnker).

Ruta: GET /api/v1/health

No es un "OK" estático: verifica conectividad rápida a Supabase.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.health_checks import check_supabase_rest

router = APIRouter()

@router.get("/health", include_in_schema=False)
async def health_v1() -> JSONResponse:
    """
    GET /health (rápido)

    - Hace un ping barato al REST de Supabase (PostgREST) usando la service key.
    - 200 OK si hay conectividad, 503 Service Unavailable si el búnker está degradado.

    Nota: PostgREST no ofrece un `SELECT 1` directo; este check equivale a un ping
    de disponibilidad del endpoint REST de Supabase.
    """
    settings = get_settings()
    ok, detail = await check_supabase_rest(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return JSONResponse(
        status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if ok else "degraded",
            "supabase": {"ok": ok, "detail": detail},
        },
    )

