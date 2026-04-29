"""
LogisAdvisor — contexto agregado (finanzas, CIP, VeriFactu, auditoría) + LLM.

``POST /api/v1/advisor/ask``
"""

import json
import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.api.v1.dependencies.credits import consume_credits
from app.core.plans import CostMeter
from app.schemas.advisor import AdvisorAskIn, AdvisorAskOut
from app.schemas.chat_persistence import (
    ChatMessageOut,
    ChatSessionCreateIn,
    ChatSessionOut,
)
from app.schemas.usage import MonthlyUsageOut
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
from app.services.chat_persistence_service import ChatPersistenceService
from app.services.usage_quota_service import UsageQuotaService, estimate_ai_tokens
from app.db.supabase import SupabaseAsync

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_CONTEXT_MESSAGES = 10
SUMMARY_CHAR_BUDGET = 1200
ARCHIVE_INACTIVE_DAYS = 30
RETENTION_DAYS = 180


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def execute_advisor_ask(
    *,
    payload: AdvisorAskIn,
    current_user: UserOut,
    db: SupabaseAsync,
    finance: FinanceService,
    portes: PortesService,
    audit_logs: AuditLogsService,
    maps: MapsService,
    bi: BiService,
    quotas: UsageQuotaService,
    chat_persistence: ChatPersistenceService,
) -> AdvisorAskOut | StreamingResponse:
    """
    Motor canónico de LogisAdvisor.
    Todas las rutas legacy deben delegar aquí.
    """
    eid = str(current_user.empresa_id)
    profile_id = (
        str(current_user.usuario_id).strip()
        if current_user.usuario_id is not None
        else None
    )
    # Guardrails de mantenimiento (best-effort): archivado inactivo + retención.
    try:
        await chat_persistence.archive_inactive_sessions(
            empresa_id=eid,
            inactive_days=ARCHIVE_INACTIVE_DAYS,
        )
        await chat_persistence.apply_retention_policy(
            empresa_id=eid,
            retention_days=RETENTION_DAYS,
        )
    except Exception:
        logger.warning("advisor_ask: maintenance guardrails skipped", exc_info=True)

    history: list[dict[str, str]] = []

    if payload.session_id is not None:
        session = await chat_persistence.get_session(
            empresa_id=eid,
            session_id=payload.session_id,
        )
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión de chat no encontrada para la empresa actual.",
            )
        session_id = str(payload.session_id)
        history = await chat_persistence.get_context_history(
            empresa_id=eid,
            session_id=session_id,
            max_context_messages=MAX_CONTEXT_MESSAGES,
            summary_char_budget=SUMMARY_CHAR_BUDGET,
        )
    else:
        auto_title = payload.message.strip()[:80]
        created = await chat_persistence.create_session(
            empresa_id=eid,
            created_by_profile_id=profile_id,
            title=auto_title,
        )
        session_id = str(created["id"])

    await chat_persistence.append_message(
        empresa_id=eid,
        session_id=session_id,
        created_by_profile_id=profile_id,
        role="user",
        content=payload.message,
    )
    started_at = time.perf_counter()

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
    reserved_units = estimate_ai_tokens(payload.message, contexto)

    if not payload.stream:
        try:
            quota = await quotas.consume(
                empresa_id=eid,
                meter=CostMeter.AI,
                units=reserved_units,
            )
            reply, model = await get_advisor_response(
                payload.message,
                eid,
                context=contexto,
                history=history,
            )
            await chat_persistence.append_message(
                empresa_id=eid,
                session_id=session_id,
                created_by_profile_id=profile_id,
                role="assistant",
                content=reply,
                model=model,
            )
            await audit_logs.log_sensitive_action(
                empresa_id=eid,
                table_name="advisor_interactions",
                record_id=session_id,
                action="INSERT",
                new_value={
                    "mode": "json",
                    "model": model,
                    "reserved_ai_units": reserved_units,
                    "remaining_ai_units": quota.remaining_units,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "ok",
                },
                user_id=profile_id,
            )
            return AdvisorAskOut(reply=reply, model=model, session_id=UUID(session_id))
        except RuntimeError as e:
            await audit_logs.log_sensitive_action(
                empresa_id=eid,
                table_name="advisor_interactions",
                record_id=session_id,
                action="INSERT",
                new_value={
                    "mode": "json",
                    "reserved_ai_units": reserved_units,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "error",
                    "error": str(e)[:200],
                },
                user_id=profile_id,
            )
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

    quota = await quotas.consume(
        empresa_id=eid,
        meter=CostMeter.AI,
        units=reserved_units,
    )

    async def event_stream():
        chunks: list[str] = []
        final_model: str | None = None
        try:
            async for text, model in stream_advisor_response(
                payload.message,
                eid,
                context=contexto,
                history=history,
            ):
                if text:
                    chunks.append(text)
                    yield _sse({"text": text})
                if model is not None:
                    final_model = model
                    yield _sse({"done": True, "model": model, "session_id": session_id})
            assistant_text = "".join(chunks).strip()
            if assistant_text:
                await chat_persistence.append_message(
                    empresa_id=eid,
                    session_id=session_id,
                    created_by_profile_id=profile_id,
                    role="assistant",
                    content=assistant_text,
                    model=final_model,
                )
                await audit_logs.log_sensitive_action(
                    empresa_id=eid,
                    table_name="advisor_interactions",
                    record_id=session_id,
                    action="INSERT",
                    new_value={
                        "mode": "stream",
                        "model": final_model,
                        "reserved_ai_units": reserved_units,
                        "remaining_ai_units": quota.remaining_units,
                        "latency_ms": int((time.perf_counter() - started_at) * 1000),
                        "status": "ok",
                    },
                    user_id=profile_id,
                )
        except RuntimeError as e:
            await audit_logs.log_sensitive_action(
                empresa_id=eid,
                table_name="advisor_interactions",
                record_id=session_id,
                action="INSERT",
                new_value={
                    "mode": "stream",
                    "reserved_ai_units": reserved_units,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "error",
                    "error": str(e)[:200],
                },
                user_id=profile_id,
            )
            yield _sse({"error": str(e)})
        except Exception:
            logger.exception("advisor_ask: error streaming")
            await audit_logs.log_sensitive_action(
                empresa_id=eid,
                table_name="advisor_interactions",
                record_id=session_id,
                action="INSERT",
                new_value={
                    "mode": "stream",
                    "reserved_ai_units": reserved_units,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "status": "error",
                    "error": "provider_contact_error",
                },
                user_id=profile_id,
            )
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


@router.post(
    "/ask",
    summary="LogisAdvisor: pregunta con contexto ERP (streaming SSE o JSON)",
)
@consume_credits(20)
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
    chat_persistence: ChatPersistenceService = Depends(deps.get_chat_persistence_service),
):
    return await execute_advisor_ask(
        payload=payload,
        current_user=current_user,
        db=db,
        finance=finance,
        portes=portes,
        audit_logs=audit_logs,
        maps=maps,
        bi=bi,
        quotas=quotas,
        chat_persistence=chat_persistence,
    )


@router.post(
    "/sessions",
    response_model=ChatSessionOut,
    summary="Crea una sesión de chat persistente para LogisAdvisor",
)
async def create_chat_session(
    payload: ChatSessionCreateIn,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    chat_persistence: ChatPersistenceService = Depends(deps.get_chat_persistence_service),
) -> ChatSessionOut:
    eid = str(current_user.empresa_id)
    profile_id = str(current_user.usuario_id).strip() if current_user.usuario_id else None
    row = await chat_persistence.create_session(
        empresa_id=eid,
        created_by_profile_id=profile_id,
        title=payload.title,
    )
    return ChatSessionOut.model_validate(row)


@router.get(
    "/sessions",
    response_model=list[ChatSessionOut],
    summary="Lista sesiones de chat del tenant actual",
)
async def list_chat_sessions(
    limit: int = 30,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    chat_persistence: ChatPersistenceService = Depends(deps.get_chat_persistence_service),
) -> list[ChatSessionOut]:
    eid = str(current_user.empresa_id)
    rows = await chat_persistence.list_sessions(empresa_id=eid, limit=limit)
    return [ChatSessionOut.model_validate(r) for r in rows]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
    summary="Lista mensajes de una sesión de chat del tenant actual",
)
async def list_chat_messages(
    session_id: UUID,
    limit: int = 200,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    chat_persistence: ChatPersistenceService = Depends(deps.get_chat_persistence_service),
) -> list[ChatMessageOut]:
    eid = str(current_user.empresa_id)
    session = await chat_persistence.get_session(
        empresa_id=eid,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    rows = await chat_persistence.list_messages(
        empresa_id=eid,
        session_id=session_id,
        limit=limit,
    )
    return [ChatMessageOut.model_validate(r) for r in rows]


@router.get(
    "/usage",
    response_model=MonthlyUsageOut,
    summary="Uso mensual actual de cuota (incluye ai_tokens_month)",
)
async def advisor_usage(
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    quotas: UsageQuotaService = Depends(deps.get_usage_quota_service),
) -> MonthlyUsageOut:
    eid = str(current_user.empresa_id)
    return await quotas.current_usage(empresa_id=eid)
