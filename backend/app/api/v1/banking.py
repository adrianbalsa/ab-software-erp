"""Banking & reconciliation API (GoCardless + fuzzy matching + IA)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api import deps
from app.schemas.banking import (
    BankPendingReconciliationOut,
    BankReconcileIn,
    BankReconcileOut,
    BankingConnectOut,
    BankingMovimientoOut,
    BankingOAuthCompleteOut,
    BankingSyncOut,
    ConciliationCandidate,
    CuentaBancaria,
)
from app.services.banking_orchestrator import BankingOrchestratorService, FUZZY_AUTO_MATCH_THRESHOLD
from app.schemas.conciliacion import (
    ConciliarAiOut,
    ConfirmarSugerenciaIn,
    MovimientoSugeridoOut,
)
from app.schemas.user import UserOut
from app.services.bank_service import _gocardless_configured
from app.services.banking_service import BankingService
from app.services.matching_service import MatchingService
from app.services.reconciliation_service import ReconciliationService

router = APIRouter()


def _parse_opt_date(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida (use YYYY-MM-DD)") from None


@router.get(
    "/pending-reconciliation",
    response_model=list[BankPendingReconciliationOut],
    summary="Movimientos bancarios pendientes de conciliar (con confianza IA/fuzzy)",
)
async def banking_pending_reconciliation(
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    matching: MatchingService = Depends(deps.get_matching_service),
) -> list[BankPendingReconciliationOut]:
    """
    Lista ``bank_transactions`` no conciliados con el mejor score de emparejamiento actual (motor fuzzy).
    La confirmación híbrida (LogisAdvisor + LLM) se hace vía ``POST /banking/reconcile``.
    """
    eid = str(current_user.empresa_id)
    txs = await matching.load_unreconciled_transactions(empresa_id=eid)
    out: list[BankPendingReconciliationOut] = []
    for tx in txs:
        cands = await matching.get_candidates(empresa_id=eid, transaction_id=tx.transaction_id)
        top = float(cands[0].score) if cands else 0.0
        inv_id = int(cands[0].factura_id) if cands else None
        bd = tx.booked_date_iso() or ""
        out.append(
            BankPendingReconciliationOut(
                transaction_id=tx.transaction_id,
                amount=float(tx.amount),
                currency=str(tx.currency or "EUR")[:8],
                booking_date=str(bd)[:10] if bd else "",
                description=tx.description,
                ia_confidence=round(top, 4),
                best_invoice_id=inv_id,
            )
        )
    return out


@router.get("/connect", response_model=BankingConnectOut)
async def banking_connect(
    institution_id: str = Query(
        ...,
        min_length=4,
        description="ID institución GoCardless (p. ej. SANDBOXFINANCE_SFIN0000)",
    ),
    redirect_url: str | None = Query(
        default=None,
        description="URL de retorno OAuth (por defecto PUBLIC_APP_URL/bancos/callback)",
    ),
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: BankingService = Depends(deps.get_banking_service),
) -> BankingConnectOut:
    """
    Genera el enlace de autorización bancaria (GoCardless Bank Account Data).
    Solo administradores de la empresa.
    """
    if not _gocardless_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración bancaria no configurada (GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY)",
        )
    try:
        out = await service.create_requisition(
            empresa_id=str(current_user.empresa_id),
            institution_id=institution_id,
            redirect_url=redirect_url,
        )
        return BankingConnectOut(**out)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/accounts", response_model=list[CuentaBancaria])
async def banking_list_accounts(
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: BankingService = Depends(deps.get_banking_service),
) -> list[CuentaBancaria]:
    """Cuentas sincronizadas / enlazadas (GoCardless Bank Account Data)."""
    if not _gocardless_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración bancaria no configurada (GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY)",
        )
    try:
        rows = await service.list_accounts(empresa_id=str(current_user.empresa_id))
        return [CuentaBancaria.from_list_account_dict(r) for r in rows]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/transactions", response_model=list[BankingMovimientoOut])
async def banking_fetch_transactions(
    days: int = Query(default=90, ge=1, le=365, description="Días hacia atrás desde hoy"),
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: BankingService = Depends(deps.get_banking_service),
) -> list[BankingMovimientoOut]:
    """Descarga y persiste movimientos recientes; devuelve el lote importado (metadatos)."""
    if not _gocardless_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración bancaria no configurada (GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY)",
        )
    try:
        rows = await service.fetch_transactions(empresa_id=str(current_user.empresa_id), days=days)
        return [BankingMovimientoOut(**r) for r in rows]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/oauth/complete", response_model=BankingOAuthCompleteOut)
async def banking_oauth_complete(
    ref: str = Query(..., min_length=8, description="requisition_id devuelto por GoCardless en el redirect (?ref=)"),
    days: int = Query(default=90, ge=1, le=365),
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: BankingService = Depends(deps.get_banking_service),
) -> BankingOAuthCompleteOut:
    """Completa el flujo tras el redirect: valida ``ref``, sincroniza cuentas y movimientos."""
    if not _gocardless_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración bancaria no configurada (GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY)",
        )
    try:
        out = await service.complete_oauth_redirect(
            empresa_id=str(current_user.empresa_id),
            ref=ref,
            days=days,
        )
        return BankingOAuthCompleteOut(
            requisition_id=out["requisition_id"],
            accounts=[CuentaBancaria.from_list_account_dict(a) for a in out["accounts"]],
            transactions_imported=int(out["transactions_imported"]),
            transactions=[BankingMovimientoOut(**t) for t in out["transactions"]],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/sync", response_model=BankingSyncOut)
async def banking_sync(
    date_from: str | None = Query(default=None, description="YYYY-MM-DD inicio ventana movimientos"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD fin ventana movimientos"),
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: BankingService = Depends(deps.get_banking_service),
) -> BankingSyncOut:
    """
    Descarga movimientos, los persiste y ejecuta conciliación automática (importe exacto + número en concepto).
    Solo administradores de la empresa.
    """
    if not _gocardless_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración bancaria no configurada (GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY)",
        )
    df = _parse_opt_date(date_from)
    dt = _parse_opt_date(date_to)
    try:
        r = await service.sincronizar_y_conciliar(
            empresa_id=str(current_user.empresa_id),
            date_from=df,
            date_to=dt,
        )
        return BankingSyncOut(
            transacciones_procesadas=r.transacciones_procesadas,
            coincidencias=r.coincidencias,
            detalle=r.detalle,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post(
    "/reconcile",
    response_model=BankReconcileOut,
    summary="Conciliación fuzzy y/o orquestador híbrido (fuzzy + IA bajo demanda)",
)
async def banking_reconcile(
    body: BankReconcileIn,
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: MatchingService = Depends(deps.get_matching_service),
    orchestrator: BankingOrchestratorService = Depends(deps.get_banking_orchestrator),
) -> BankReconcileOut:
    """
    Sin ``transaction_id`` / ``transaction_ids``: mismo comportamiento histórico (lote fuzzy con ``threshold``).

    Con identificadores: orquestador híbrido por movimiento — fuzzy >0,95 como AUTO; si no aplica y el mejor
    fuzzy está en (0,40, 0,95], IA con los 5 mejores candidatos fuzzy; ``asyncio.gather`` si hay varios IDs.
    """
    empresa_id = str(current_user.empresa_id)
    tx_ids: list[UUID] = []
    if body.transaction_id is not None:
        tx_ids = [body.transaction_id]
    elif body.transaction_ids is not None:
        tx_ids = list(body.transaction_ids)

    try:
        if not tx_ids:
            out = await service.auto_match(
                empresa_id=empresa_id,
                commit=body.commit,
                threshold=body.threshold,
            )
            return BankReconcileOut(
                threshold_used=float(out["threshold_used"]),
                commit=bool(out["commit"]),
                suggestions=[ConciliationCandidate(**s) for s in out["suggestions"]],
                committed_pairs=int(out["committed_pairs"]),
                hybrid_results=[],
                orchestration_mode="batch_fuzzy",
            )

        hybrid_results, committed = await orchestrator.process_batch(
            empresa_id=empresa_id,
            transaction_ids=tx_ids,
            commit=body.commit,
            ai_commit_min_confidence=body.ai_commit_min_confidence,
        )
        return BankReconcileOut(
            threshold_used=float(FUZZY_AUTO_MATCH_THRESHOLD),
            commit=body.commit,
            suggestions=[],
            committed_pairs=int(committed),
            hybrid_results=hybrid_results,
            orchestration_mode="hybrid",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "/reconciliation/ai",
    response_model=ConciliarAiOut,
    summary="Conciliación asistida por IA (LLM)",
)
async def banking_reconcile_ai(
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner")),
    service: ReconciliationService = Depends(deps.get_reconciliation_service),
) -> ConciliarAiOut:
    """Genera sugerencias con LLM y las persiste cuando los IDs son válidos."""
    try:
        return await service.ejecutar_conciliacion_ia_completa(empresa_id=str(current_user.empresa_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/reconciliation/suggestions",
    response_model=list[MovimientoSugeridoOut],
    summary="Sugerencias de conciliación pendientes",
)
async def banking_reconciliation_suggestions(
    current_user: UserOut = Depends(deps.require_role("owner")),
    service: ReconciliationService = Depends(deps.get_reconciliation_service),
) -> list[MovimientoSugeridoOut]:
    """Movimientos en estado Sugerido para revisión en la UI."""
    rows = await service.listar_movimientos_sugeridos(empresa_id=str(current_user.empresa_id))
    return [MovimientoSugeridoOut(**r) for r in rows]


@router.post(
    "/reconciliation/suggestions/confirm",
    summary="Confirmar o rechazar sugerencia de conciliación",
)
async def banking_reconciliation_confirm(
    body: ConfirmarSugerenciaIn,
    current_user: UserOut = Depends(deps.bind_write_context),
    _: UserOut = Depends(deps.require_role("owner")),
    service: ReconciliationService = Depends(deps.get_reconciliation_service),
) -> Response:
    """Aprueba o rechaza una sugerencia IA."""
    try:
        await service.confirmar_sugerencia(
            empresa_id=str(current_user.empresa_id),
            movimiento_id=body.movimiento_id,
            aprobar=body.aprobar,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
