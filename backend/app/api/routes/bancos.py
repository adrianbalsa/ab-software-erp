from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import deps
from app.schemas.banco import BancoConectarOut, BancoSyncOut
from app.schemas.user import UserOut
from app.services.bank_service import BankService, _gocardless_configured

router = APIRouter()


def _parse_opt_date(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida (use YYYY-MM-DD)") from None


@router.get("/conectar", response_model=BancoConectarOut)
async def bancos_conectar(
    institution_id: str = Query(..., min_length=4, description="ID institución GoCardless (p. ej. SANDBOXFINANCE_SFIN0000)"),
    redirect_url: str | None = Query(
        default=None,
        description="URL de retorno OAuth (por defecto PUBLIC_APP_URL/bancos/callback)",
    ),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: BankService = Depends(deps.get_bank_service),
) -> BancoConectarOut:
    """
    Genera el enlace de autorización bancaria (GoCardless Bank Account Data).
    Persiste ``requisition_id`` y token de acceso **cifrados** por empresa.
    """
    if not _gocardless_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración bancaria no configurada (GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY)",
        )
    try:
        out = await service.get_auth_link(
            empresa_id=str(current_user.empresa_id),
            institution_id=institution_id,
            redirect_url=redirect_url,
        )
        return BancoConectarOut(**out)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/sincronizar", response_model=BancoSyncOut)
async def bancos_sincronizar(
    date_from: str | None = Query(default=None, description="YYYY-MM-DD inicio ventana movimientos"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD fin ventana movimientos"),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: BankService = Depends(deps.get_bank_service),
) -> BancoSyncOut:
    """
    Descarga movimientos bancarios y ejecuta conciliación automática con facturas ``estado_cobro=emitida``
    (importe y fecha ±3 días). Las coincidencias marcan la factura como ``cobrada`` y guardan ``pago_id``.
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
        return BancoSyncOut(
            transacciones_procesadas=r.transacciones_procesadas,
            coincidencias=r.coincidencias,
            detalle=r.detalle,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
