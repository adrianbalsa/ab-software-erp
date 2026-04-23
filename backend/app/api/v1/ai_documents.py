from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api import deps
from app.schemas.document_ai import AskAdvisorRequest, AskAdvisorResponse, ProcessDocumentResponse
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.advisor_service import economic_advisor_rag_ask
from app.services.ocr_service import vampire_radar_process_document

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/process-document", response_model=ProcessDocumentResponse)
async def process_document(
    file: UploadFile = File(...),
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager", "gestor", "admin")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> ProcessDocumentResponse:
    """
    Vampire Radar: extrae datos fiscales de imagen (ticket/factura), genera resumen e indexa en pgvector.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Archivo vacío")
    try:
        return await vampire_radar_process_document(
            image_bytes=content,
            empresa_id=str(current_user.empresa_id),
            db=db,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("process_document: error Vampire Radar")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo procesar el documento.",
        ) from None


@router.post("/ask-advisor", response_model=AskAdvisorResponse)
async def ask_advisor(
    payload: AskAdvisorRequest,
    _: UserOut = Depends(deps.bind_write_context),
    __role: UserOut = Depends(deps.require_role("owner", "traffic_manager", "gestor", "admin")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> AskAdvisorResponse:
    """
    Economic Advisor: RAG sobre ``document_embeddings`` del tenant (JWT + ``app_current_empresa_id``).
    """
    try:
        answer, model, sources = await economic_advisor_rag_ask(
            db,
            question=payload.question,
            match_count=payload.match_count,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception:
        logger.exception("ask_advisor: error RAG")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar el asesor económico.",
        ) from None

    return AskAdvisorResponse(answer=answer, model=model, sources=sources)
