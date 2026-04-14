"""Conciliación bancaria automática (motor de emparejamiento probabilístico)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.schemas.banco import BankAutoMatchIn, BankAutoMatchOut, BankMatchSuggestionResult
from app.schemas.user import UserOut
from app.services.matching_service import MatchingService

router = APIRouter()


@router.post(
    "/auto-match",
    response_model=BankAutoMatchOut,
    summary="Sugerir o aplicar conciliación banco ↔ facturas (S_c > umbral)",
)
async def bank_auto_match(
    body: BankAutoMatchIn,
    current_user: UserOut = Depends(deps.require_admin_active_write_user),
    service: MatchingService = Depends(deps.get_matching_service),
) -> BankAutoMatchOut:
    """
    Por defecto solo devuelve sugerencias (no persiste). Con ``commit=true`` enlaza movimientos
    y marca facturas como cobradas cuando S_c supera el umbral (importe exacto + fuzzy + ventana ±30d).
    """
    try:
        out = await service.auto_match(
            empresa_id=str(current_user.empresa_id),
            commit=body.commit,
            threshold=body.threshold,
        )
        return BankAutoMatchOut(
            threshold_used=float(out["threshold_used"]),
            commit=bool(out["commit"]),
            suggestions=[BankMatchSuggestionResult(**s) for s in out["suggestions"]],
            committed_pairs=int(out["committed_pairs"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
