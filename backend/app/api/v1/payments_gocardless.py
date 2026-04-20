"""Endpoints de pagos GoCardless (customer + pago puntual por factura)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api import deps
from app.core.config import get_settings
from app.schemas.user import UserOut
from app.services.payment_service import (
    PaymentDomainError,
    PaymentIntegrationError,
    PaymentService,
)

router = APIRouter()


class GoCardlessCustomerCreateIn(BaseModel):
    given_name: str = Field(..., min_length=1, max_length=120)
    family_name: str = Field(..., min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    metadata: dict[str, str] | None = None


class GoCardlessCustomerCreateOut(BaseModel):
    customer_id: str
    empresa_id: str
    created_at: str


class GoCardlessOneOffPaymentIn(BaseModel):
    factura_id: int = Field(..., gt=0)
    customer_id: str = Field(..., min_length=2, max_length=120)
    mandate_id: str = Field(..., min_length=2, max_length=120)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class GoCardlessOneOffPaymentOut(BaseModel):
    factura_id: int
    empresa_id: str
    customer_id: str
    payment_id: str
    status: str
    amount: str
    currency: str
    timestamp: str


class SetupMandateOut(BaseModel):
    """Si ya hay mandato activo, ``redirect_url`` va vacío y ``has_active_mandate`` es True."""

    redirect_url: str = ""
    has_active_mandate: bool = False


@router.post(
    "/customers",
    response_model=GoCardlessCustomerCreateOut,
    summary="Crear customer en GoCardless",
)
async def create_gocardless_customer(
    body: GoCardlessCustomerCreateIn,
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: PaymentService = Depends(deps.get_payment_service),
) -> GoCardlessCustomerCreateOut:
    try:
        out = await service.create_customer(
            empresa_id=str(current_user.empresa_id),
            given_name=body.given_name,
            family_name=body.family_name,
            email=body.email,
            metadata=body.metadata,
        )
    except PaymentDomainError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaymentIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return GoCardlessCustomerCreateOut(**out)


@router.post(
    "/one-off",
    response_model=GoCardlessOneOffPaymentOut,
    summary="Crear pago puntual GoCardless desde factura",
)
async def create_gocardless_one_off_payment(
    body: GoCardlessOneOffPaymentIn,
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: PaymentService = Depends(deps.get_payment_service),
) -> GoCardlessOneOffPaymentOut:
    try:
        out: dict[str, Any] = await service.create_one_off_payment_from_invoice(
            empresa_id=str(current_user.empresa_id),
            factura_id=body.factura_id,
            customer_id=body.customer_id,
            mandate_id=body.mandate_id,
            currency=body.currency,
        )
    except PaymentDomainError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaymentIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return GoCardlessOneOffPaymentOut(**out)


@router.post(
    "/mandates/setup",
    response_model=SetupMandateOut,
    summary="Iniciar flujo de mandato SEPA (GoCardless)",
)
async def setup_gocardless_mandate(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    service: PaymentService = Depends(deps.get_payment_service),
) -> SetupMandateOut:
    cliente_id = portal_user.cliente_id
    if cliente_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cliente portal no vinculado.")
    base = (get_settings().PUBLIC_APP_URL or "http://localhost:3000").rstrip("/")
    success_url = f"{base}/portal-cliente/facturas?setup=success"
    try:
        out = await service.create_mandate_setup_flow(
            cliente_id=str(cliente_id),
            success_url=success_url,
        )
    except PaymentDomainError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PaymentIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return SetupMandateOut(
        redirect_url=str(out.get("redirect_url") or ""),
        has_active_mandate=bool(out.get("has_active_mandate")),
    )

