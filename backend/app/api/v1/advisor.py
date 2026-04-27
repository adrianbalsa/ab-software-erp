"""
LogisAdvisor — contexto agregado (finanzas, CIP, VeriFactu, auditoría) + LLM.

``POST /api/v1/advisor/ask``
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.core.plans import CostMeter
from app.schemas.advisor import AdvisorAskIn, AdvisorAskOut
from app.schemas.user import UserOut
from app.services.advisor_service import (
    gather_advisor_context,
    get_advisor_response,
    mask_advisor_context_for_rbac,
    openai_configured,
    stream_advisor_response,
)
from app.services.audit_logs_service import AuditLogsService
from app.services.bi_service import BiService
from app.services.finance_service import FinanceService
from app.services.maps_service import MapsService
from app.services.portes_service import PortesService
from app.services.usage_quota_service import UsageQuotaService, estimate_ai_tokens
from app.db.supabase import SupabaseAsync

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/ask",
    summary="LogisAdvisor: pregunta con contexto ERP (streaming SSE o JSON)",
)
async def advisor_ask(
    payload: AdvisorAskIn,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
    finance: FinanceService = Depends(deps.get_finance_service),
    portes: PortesService = Depends(deps.get_portes_service),
    audit_logs: AuditLogsService = Depends(deps.get_audit_logs_service),
    maps: MapsService = Depends(deps.get_maps_service),
    bi: BiService = Depends(deps.get_bi_service),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
):
    """
    Contexto: EBITDA, serie 6m, matriz CIP (y heurística “vampiros”), tesorería/cashflow,
    flota por normativa Euro (Euro III destacado), cadena VeriFactu, últimos audit logs,
    e inteligencia BI (DSO, trayectos con η inferior a 1, ranking de presión de cobro por cliente).
    """
    eid = str(current_user.empresa_id)

    if not openai_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LogisAdvisor no configurado (faltan credenciales LLM en el servidor, p. ej. OPENAI_API_KEY o ANTHROPIC_API_KEY).",
        )

    try:
        contexto = await gather_advisor_context(
            db=db,
            empresa_id=eid,
            finance=finance,
            portes=portes,
            audit_logs=audit_logs,
            maps=maps,
            bi=bi,
        )
        contexto = mask_advisor_context_for_rbac(
            contexto,
            rbac_role=str(current_user.rbac_role or ""),
        )
    except Exception:
        logger.exception("advisor_ask: error gather_advisor_context")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo construir el contexto para LogisAdvisor.",
        ) from None

    if not payload.stream:
        try:
            await quotas.consume(
                empresa_id=eid,
                meter=CostMeter.AI,
                units=estimate_ai_tokens(payload.message, contexto),
            )
            reply, model = await get_advisor_response(
                payload.message,
                eid,
                context=contexto,
            )
            return AdvisorAskOut(reply=reply, model=model)
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

    await quotas.consume(
        empresa_id=eid,
        meter=CostMeter.AI,
        units=estimate_ai_tokens(payload.message, contexto),
    )

    async def event_stream():
        try:
            async for text, model in stream_advisor_response(
                payload.message,
                eid,
                context=contexto,
            ):
                if text:
                    yield _sse({"text": text})
                if model is not None:
                    yield _sse({"done": True, "model": model})
        except RuntimeError as e:
            yield _sse({"error": str(e)})
        except Exception:
            logger.exception("advisor_ask: error streaming")
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
