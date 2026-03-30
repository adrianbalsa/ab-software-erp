"""Datos JSON para PDF comercial VeriFactu (cliente @react-pdf/renderer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.schemas.factura import FacturaPdfDataOut
from app.schemas.user import UserOut
from app.services.facturas_service import FacturasService

router = APIRouter()


@router.get("/{factura_id}/pdf-data", response_model=FacturaPdfDataOut)
async def get_factura_pdf_data(
    factura_id: int,
    current_user: UserOut = Depends(deps.require_role("owner")),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="facturas", path_param="factura_id")
    ),
    service: FacturasService = Depends(deps.get_facturas_service),
) -> FacturaPdfDataOut:
    """
    Información estructurada de la factura + ``verifactu_qr_base64`` (PNG en Base64, URL SREI VeriFactu).
    Totales redondeados con el Math Engine; metadatos del último ``verifactu_envios`` si existe.
    """
    try:
        return await service.get_factura_pdf_data(
            empresa_id=current_user.empresa_id,
            factura_id=factura_id,
        )
    except ValueError as e:
        if "no encontrada" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
