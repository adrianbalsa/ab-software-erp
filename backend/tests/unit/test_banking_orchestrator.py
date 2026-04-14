"""Tests del orquestador híbrido (sin base de datos)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from pydantic import ValidationError

from app.schemas.banking import BankReconcileIn, ConciliationCandidate, ConciliationMethod, Transaccion
from app.services.banking_orchestrator import BankingOrchestratorService, FUZZY_AUTO_MATCH_THRESHOLD


def test_bank_reconcile_in_rejects_both_id_fields() -> None:
    u1, u2 = uuid4(), uuid4()
    with pytest.raises(ValidationError):
        BankReconcileIn(transaction_id=u1, transaction_ids=[u2])


def _cand(tid: str, score: float, fid: int = 1) -> ConciliationCandidate:
    return ConciliationCandidate(
        transaction_id=tid,
        factura_id=fid,
        score=score,
        reference_score=0.5,
        date_score=0.5,
        amount=100.0,
    )


@pytest.mark.asyncio
async def test_orchestrator_fuzzy_auto_high_commit() -> None:
    from uuid import UUID

    tid = str(uuid4())
    tx = Transaccion(transaction_id=tid, amount=Decimal("100.00"))
    match = MagicMock()
    match.get_unreconciled_transaction = AsyncMock(return_value=tx)
    match.get_candidates = AsyncMock(return_value=[_cand(tid, FUZZY_AUTO_MATCH_THRESHOLD + 0.01)])
    match.commit_matches = AsyncMock(return_value=1)

    recon = MagicMock()
    orch = BankingOrchestratorService(match, recon)
    tx_uuid = UUID(tid)

    result, n = await orch.process_reconciliation(
        empresa_id="e1",
        transaction_id=tx_uuid,
        commit=True,
    )
    assert n == 1
    assert result.method == ConciliationMethod.FUZZY_AUTO
    assert result.candidate is not None
    match.commit_matches.assert_awaited_once()
    recon.suggest_bank_pair_orchestrator_llm.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_no_llm_below_floor() -> None:
    tid = str(uuid4())
    tx = Transaccion(transaction_id=tid, amount=Decimal("50.00"))
    match = MagicMock()
    match.get_unreconciled_transaction = AsyncMock(return_value=tx)
    match.get_candidates = AsyncMock(return_value=[_cand(tid, 0.35)])

    recon = MagicMock()
    orch = BankingOrchestratorService(match, recon)

    from uuid import UUID

    result, n = await orch.process_reconciliation(empresa_id="e1", transaction_id=UUID(tid))
    assert n == 0
    assert result.method == ConciliationMethod.NONE
    recon.suggest_bank_pair_orchestrator_llm.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_calls_llm_in_band() -> None:
    tid = str(uuid4())
    tx = Transaccion(transaction_id=tid, amount=Decimal("75.00"))
    match = MagicMock()
    match.get_unreconciled_transaction = AsyncMock(return_value=tx)
    match.get_candidates = AsyncMock(return_value=[_cand(tid, 0.75)])
    match.commit_matches = AsyncMock(return_value=1)

    recon = MagicMock()
    chosen = _cand(tid, 0.91, fid=2)
    recon.suggest_bank_pair_orchestrator_llm = AsyncMock(return_value=(chosen, "ok", None))

    orch = BankingOrchestratorService(match, recon)

    from uuid import UUID

    result, n = await orch.process_reconciliation(
        empresa_id="e1",
        transaction_id=UUID(tid),
        commit=True,
        ai_commit_min_confidence=0.90,
    )
    assert result.method == ConciliationMethod.AI
    assert result.final_confidence == pytest.approx(0.91)
    assert n == 1
    recon.suggest_bank_pair_orchestrator_llm.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_batch_calls_each_id() -> None:
    match = MagicMock()
    recon = MagicMock()
    orch = BankingOrchestratorService(match, recon)
    stub = AsyncMock(
        side_effect=[
            (MagicMock(method=ConciliationMethod.NONE), 0),
            (MagicMock(method=ConciliationMethod.NONE), 0),
        ]
    )
    orch.process_reconciliation = stub  # type: ignore[method-assign]

    u1, u2 = uuid4(), uuid4()
    results, committed = await orch.process_batch(
        empresa_id="e1",
        transaction_ids=[u1, u2],
        commit=False,
    )
    assert len(results) == 2
    assert committed == 0
    assert stub.await_count == 2
