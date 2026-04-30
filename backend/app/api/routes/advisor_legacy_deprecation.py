"""
Rutas legacy bajo ``/ai/*`` retiradas del producto.

El flujo canónico es ``POST /api/v1/advisor/ask`` (ver ``app.api.v1.advisor``).
Se mantienen estos endpoints solo para devolver **410 Gone** con pistas de migración.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

_LEGACY_DETAIL: dict[str, str] = {
    "error": "legacy_endpoint_removed",
    "canonical_method": "POST",
    "canonical_path": "/api/v1/advisor/ask",
    "body_hint": '{"message": "<texto>", "stream": true|false, "session_id": null|<uuid>}',
}


@router.post("/chat", include_in_schema=False, deprecated=True)
async def legacy_ai_chat_gone() -> None:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_LEGACY_DETAIL)


@router.post("/consult", include_in_schema=False, deprecated=True)
async def legacy_ai_consult_gone() -> None:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_LEGACY_DETAIL)
