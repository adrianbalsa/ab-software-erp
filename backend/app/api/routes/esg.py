from __future__ import annotations

import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.user import UserOut
from app.services.esg_service import EsgService
from app.services.pdf_esg_service import generar_certificado_huella_carbono_pdf

router = APIRouter()


@router.get("/reporte-certificado/")
async def descargar_certificado_huella_carbono(
    mes: int = Query(..., ge=1, le=12, description="Mes calendario (1–12)"),
    anio: int = Query(..., ge=2020, le=2100, description="Año (YYYY)"),
    current_user: UserOut = Depends(deps.require_admin_user),
    _quota: None = Depends(deps.check_quota_limit("esg")),
    service: EsgService = Depends(deps.get_esg_service),
) -> StreamingResponse:
    """
    PDF «Certificado de Huella de Carbono» (licitaciones) con sello digital AB Logistics OS.

    Solo **administradores** del tenant. Requiere plan con ESG (Enterprise) vía cuota.
    """
    eid = str(current_user.empresa_id)
    huella = await service.calcular_huella_carbono_mensual(
        empresa_id=eid,
        mes=mes,
        anio=anio,
    )
    nombre = await service.nombre_empresa_publico(empresa_id=eid)
    pdf_bytes = generar_certificado_huella_carbono_pdf(
        empresa_nombre=nombre,
        empresa_id=eid,
        huella=huella,
    )
    safe = f"Certificado_Huella_CO2_{anio}{mes:02d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )
