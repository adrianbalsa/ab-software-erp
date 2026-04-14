"""
Orquestación híbrida de conciliación bancaria: fuzzy de alto valor → IA focalizada (pocos tokens).
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.schemas.banking import ConciliationCandidate, ConciliationMethod, ConciliationResult, Transaccion
from app.services.matching_service import MatchingService
from app.services.reconciliation_service import ReconciliationService

_log = logging.getLogger(__name__)

FUZZY_AUTO_MATCH_THRESHOLD = 0.95
FUZZY_AI_FLOOR = 0.40
TOP_FUZZY_FOR_LLM = 5


class BankingOrchestratorService:
    """Conciliación por transacción: primero fuzzy; si hace falta, LLM solo con top-K fuzzy."""

    def __init__(
        self,
        matching: MatchingService,
        reconciliation: ReconciliationService,
    ) -> None:
        self._matching = matching
        self._recon = reconciliation

    async def process_reconciliation(
        self,
        *,
        empresa_id: str,
        transaction_id: UUID,
        commit: bool = False,
        ai_commit_min_confidence: float = 0.85,
    ) -> tuple[ConciliationResult, int]:
        """
        Devuelve ``(resultado, committed_delta)`` con ``committed_delta`` 0 o 1 si se persistió un par.
        """
        tid_str = str(transaction_id).strip()
        eid = str(empresa_id or "").strip()

        tx_row: Transaccion | None = await self._matching.get_unreconciled_transaction(
            empresa_id=eid,
            transaction_id=tid_str,
        )
        if tx_row is None:
            return (
                ConciliationResult(
                    transaction_id=tid_str,
                    method=ConciliationMethod.NONE,
                    final_confidence=0.0,
                    candidate=None,
                    error="Movimiento no encontrado, ya conciliado o importe cero",
                ),
                0,
            )

        candidates = await self._matching.get_candidates(empresa_id=eid, transaction_id=tid_str)
        best = candidates[0] if candidates else None

        if best is not None and best.score > FUZZY_AUTO_MATCH_THRESHOLD:
            n = 0
            if commit:
                n = await self._matching.commit_matches(empresa_id=eid, matches=[best])
            return (
                ConciliationResult(
                    transaction_id=tid_str,
                    method=ConciliationMethod.FUZZY_AUTO,
                    final_confidence=float(best.score),
                    candidate=best,
                ),
                n,
            )

        if best is None or best.score <= FUZZY_AI_FLOOR:
            return (
                ConciliationResult(
                    transaction_id=tid_str,
                    method=ConciliationMethod.NONE,
                    final_confidence=float(best.score) if best is not None else 0.0,
                    candidate=None,
                ),
                0,
            )

        tier = [c for c in candidates if c.score > FUZZY_AI_FLOOR]
        top_k = tier[:TOP_FUZZY_FOR_LLM]

        cand_llm, razon, err = await self._recon.suggest_bank_pair_orchestrator_llm(
            empresa_id=eid,
            transaction=tx_row,
            top_candidates=top_k,
        )
        if err:
            _log.warning("banking_orchestrator: IA no disponible o error tx=%s: %s", tid_str, err)
            return (
                ConciliationResult(
                    transaction_id=tid_str,
                    method=ConciliationMethod.NONE,
                    final_confidence=float(best.score),
                    candidate=None,
                    error=err,
                ),
                0,
            )

        if cand_llm is None:
            return (
                ConciliationResult(
                    transaction_id=tid_str,
                    method=ConciliationMethod.NONE,
                    final_confidence=float(best.score),
                    candidate=None,
                    razonamiento_ia=razon,
                ),
                0,
            )

        n = 0
        if commit and float(cand_llm.score) >= float(ai_commit_min_confidence):
            n = await self._matching.commit_matches(empresa_id=eid, matches=[cand_llm])

        return (
            ConciliationResult(
                transaction_id=tid_str,
                method=ConciliationMethod.AI,
                final_confidence=float(cand_llm.score),
                candidate=cand_llm,
                razonamiento_ia=razon,
            ),
            n,
        )

    async def process_batch(
        self,
        *,
        empresa_id: str,
        transaction_ids: list[UUID],
        commit: bool = False,
        ai_commit_min_confidence: float = 0.85,
    ) -> tuple[list[ConciliationResult], int]:
        """Procesa en paralelo; el recuento ``committed`` es el total de pares persistidos."""
        if not transaction_ids:
            return [], 0

        async def _one(uid: UUID) -> tuple[ConciliationResult, int]:
            return await self.process_reconciliation(
                empresa_id=empresa_id,
                transaction_id=uid,
                commit=commit,
                ai_commit_min_confidence=ai_commit_min_confidence,
            )

        parts = await asyncio.gather(*[_one(u) for u in transaction_ids])
        results = [p[0] for p in parts]
        committed = sum(p[1] for p in parts)
        return results, committed
