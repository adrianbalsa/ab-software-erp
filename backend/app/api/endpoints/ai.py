from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.core.plans import CostMeter
from app.schemas.ai import AiConsultRequest, AiConsultResponse
from app.schemas.user import UserOut
from app.services.ai_service import LogisAdvisorService
from app.services.usage_quota_service import UsageQuotaService, estimate_ai_tokens

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/consult", response_model=AiConsultResponse)
async def consult_ai(
    payload: AiConsultRequest,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service: LogisAdvisorService = Depends(deps.get_logis_advisor_service),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
) -> AiConsultResponse:
    eid = str(current_user.empresa_id)
    if payload.empresa_id is not None and str(payload.empresa_id) != eid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empresa_id no coincide con la sesión",
        )
    if not service.openai_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asistente IA no configurado (faltan credenciales OpenAI/Gemini).",
        )

    try:
        context = payload.data_context or await service.build_data_context(empresa_id=eid)
        await quotas.consume(
            empresa_id=eid,
            meter=CostMeter.AI,
            units=estimate_ai_tokens(payload.query, context),
        )
        result = await service.generate_diagnostic(
            data_context=context,
            user_query=payload.query,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception:
        logger.exception("consult_ai: error generando diagnóstico")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo generar el diagnóstico IA.",
        ) from None

    return AiConsultResponse(**result)
