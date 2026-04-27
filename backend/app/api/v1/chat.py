from __future__ import annotations

import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.core.plans import CostMeter
from app.schemas.ai import AiChatRequest
from app.schemas.user import UserOut
from app.services.ai_service import LogisAdvisorService
from app.services.esg_audit_service import EsgAuditService
from app.services.finance_service import FinanceService
from app.services.usage_quota_service import UsageQuotaService, estimate_ai_tokens

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/advisor",
    summary="LogisAdvisor (respuesta SSE en streaming)",
)
async def advisor_chat_stream(
    payload: AiChatRequest,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    finance: FinanceService = Depends(deps.get_finance_service),
    esg_audit: EsgAuditService = Depends(deps.get_esg_audit_service),
    advisor: LogisAdvisorService = Depends(deps.get_logis_advisor_service),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
):
    """
    LogisAdvisor con contexto inyectado: ``economic_insights_advanced`` + auditoría ESG del periodo.
    Respuesta en streaming (SSE).
    """
    eid = str(current_user.empresa_id)
    if payload.empresa_id is not None and str(payload.empresa_id) != eid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empresa_id no coincide con la sesión",
        )

    if not advisor.openai_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asistente IA no configurado (falta OPENAI_API_KEY en el servidor).",
        )

    hoy = date.today()
    fecha_inicio = date(hoy.year, 1, 1)
    fecha_fin = hoy

    try:
        fin = await finance.economic_insights_advanced(empresa_id=eid, hoy=hoy)
        esg = await esg_audit.audit_report(
            empresa_id=eid,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
    except Exception:
        logger.exception("advisor_chat_stream: error cargando contexto")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron cargar los datos para el asesor.",
        ) from None

    contexto = {
        "economic_insights_advanced": fin.model_dump(mode="json"),
        "esg_audit_ytd": esg.model_dump(mode="json"),
        "nota_periodo_esg": "Auditoría ESG: año natural en curso (1 ene → hoy).",
    }
    contexto_json = json.dumps(contexto, ensure_ascii=False)

    hist = [{"role": m.role, "content": m.content} for m in payload.history]

    await quotas.consume(
        empresa_id=eid,
        meter=CostMeter.AI,
        units=estimate_ai_tokens(payload.message, hist, contexto_json),
    )

    async def event_stream():
        try:
            async for text, model in advisor.stream_advisor_chat(
                empresa_id=eid,
                user_message=payload.message,
                history=hist,
                contexto_datos_json=contexto_json,
            ):
                if text:
                    yield _sse({"text": text})
                if model is not None:
                    yield _sse({"done": True, "model": model})
        except RuntimeError as e:
            yield _sse({"error": str(e)})
        except Exception:
            logger.exception("advisor_chat_stream: fallo en streaming")
            yield _sse({"error": "Error al contactar el proveedor de IA."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
