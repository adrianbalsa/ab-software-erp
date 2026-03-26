from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.schemas.ai import AiChatRequest, AiChatResponse
from app.schemas.user import UserOut
from app.services.ai_service import LogisAdvisorService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=AiChatResponse)
async def ai_chat(
    payload: AiChatRequest,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: LogisAdvisorService = Depends(deps.get_logis_advisor_service),
) -> AiChatResponse:
    """
    LogisAdvisor: chat con herramientas de negocio (finanzas, facturación, flota/ESG).
    El **tenant** lo fija el JWT; ``empresa_id`` en el body solo se valida si se envía.
    """
    eid = str(current_user.empresa_id)
    if payload.empresa_id is not None and str(payload.empresa_id) != eid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empresa_id no coincide con la sesión",
        )

    if not service.openai_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asistente IA no configurado (falta OPENAI_API_KEY en el servidor).",
        )

    hist = [{"role": m.role, "content": m.content} for m in payload.history]

    try:
        reply, model = await service.chat(
            empresa_id=eid,
            user_message=payload.message,
            history=hist,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except Exception:
        logger.exception("ai_chat: fallo al invocar al proveedor de IA")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al contactar el proveedor de IA.",
        ) from None

    return AiChatResponse(reply=reply, model=model)
