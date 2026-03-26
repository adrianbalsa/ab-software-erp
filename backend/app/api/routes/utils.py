from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.health_service import perform_full_health_check

router = APIRouter(prefix="/health")


@router.get("/status")
async def health_status() -> JSONResponse:
    """
    Salud proactiva (latencia ``SELECT 1``). ``fail`` → **503** para balanceadores.
    Estados ``skipped`` y ``degraded`` responden **200**.
    """
    body = await perform_full_health_check()
    code = 503 if body.get("status") == "fail" else 200
    return JSONResponse(content=body, status_code=code)
