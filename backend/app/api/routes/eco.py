from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api import deps
from app.schemas.eco import (
    EcoCertificadoIn,
    EcoDashboardOut,
    EcoEmisionMensualOut,
    EcoFlotaSimRow,
    EcoResumenLiteOut,
    EcoSimuladorIn,
)
from app.schemas.user import UserOut
from app.services.eco_pdf_service import generar_pdf_oficial
from app.services.eco_service import (
    EUR_POR_LITRO_DIESEL_REF,
    KG_CO2_POR_LITRO_DIESEL,
    EcoService,
)
from app.services.pdf_service import (
    generar_pdf_certificado_emisiones_esg,
    generar_pdf_certificado_ruta_esg,
)

router = APIRouter()


@router.get("/dashboard/", response_model=EcoDashboardOut)
async def dashboard_esg(
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
    service: EcoService = Depends(deps.get_eco_service),
) -> EcoDashboardOut:
    """
    Agregado mensual de CO₂ de portes facturados (mes calendario actual). Plan Enterprise.
    """
    return await service.obtener_reporte_mensual(empresa_id=str(current_user.empresa_id))


class RutaLogistica(BaseModel):
    distancia_km: float
    consumo_litros_100km: float = 32.0
    tipo_combustible: str = "diesel"
    toneladas_carga: float


@router.post("/certificado-pdf", summary="Genera y descarga un certificado ESG en PDF (ruta logística)")
async def generar_certificado_pdf(
    ruta: RutaLogistica,
    _esg: None = Depends(deps.check_quota_limit("esg")),
) -> StreamingResponse:
    FACTOR_CO2_DIESEL = 2.64

    if ruta.tipo_combustible.lower() == "electrico":
        emisiones = 0.0
    elif ruta.tipo_combustible.lower() == "hibrido":
        emisiones = (
            (ruta.distancia_km / 100)
            * (ruta.consumo_litros_100km * 0.6)
            * FACTOR_CO2_DIESEL
        )
    else:
        emisiones = (ruta.distancia_km / 100) * ruta.consumo_litros_100km * FACTOR_CO2_DIESEL

    emisiones_base_antigua = (ruta.distancia_km / 100) * 40.0 * FACTOR_CO2_DIESEL
    co2_ahorrado = max(0.0, emisiones_base_antigua - emisiones)

    pdf_bytes = generar_pdf_certificado_ruta_esg(
        distancia_km=ruta.distancia_km,
        toneladas_carga=ruta.toneladas_carga,
        tipo_combustible=ruta.tipo_combustible,
        consumo_litros_100km=ruta.consumo_litros_100km,
        emisiones_kg=emisiones,
        ahorro_kg=co2_ahorrado,
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Certificado_ESG_ABLogistics.pdf"},
    )


@router.get("/emisiones-mensuales", response_model=list[EcoEmisionMensualOut])
async def emisiones_mensuales_combustible(
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
    service: EcoService = Depends(deps.get_eco_service),
) -> list[EcoEmisionMensualOut]:
    """
    Serie mensual CO₂ Scope 1 (combustible) y litros estimados — para dashboards ESG y certificados.
    """
    return await service.emisiones_combustible_por_mes(empresa_id=current_user.empresa_id)


@router.get("/resumen", response_model=EcoResumenLiteOut)
async def resumen_empresa(
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
    service: EcoService = Depends(deps.get_eco_service),
) -> EcoResumenLiteOut:
    return await service.resumen_empresa_lite(empresa_id=current_user.empresa_id)


@router.post("/simulador", response_model=EcoResumenLiteOut)
async def simular_eco(
    payload: EcoSimuladorIn,
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
    service: EcoService = Depends(deps.get_eco_service),
) -> EcoResumenLiteOut:
    """Simula tickets + flota y suma CO2 combustible real (BD) de la empresa del JWT."""
    base = EcoService.calcular_simulador_lite(payload=payload)
    co2_cb, _lit = await service.co2_emisiones_combustible_scope1(
        empresa_id=current_user.empresa_id
    )
    total_co2_kg, scope_1_kg, scope_3_kg, co2_per_ton_km = await service.dynamic_portes_summary(
        empresa_id=str(current_user.empresa_id),
    )
    return EcoResumenLiteOut(
        n_tickets=base.n_tickets,
        papel_kg=base.papel_kg,
        co2_tickets=base.co2_tickets,
        co2_flota=base.co2_flota,
        co2_combustible=float(co2_cb),
        co2_total=float(base.co2_tickets + base.co2_flota + co2_cb),
        total_co2_kg=total_co2_kg,
        scope_1_kg=scope_1_kg,
        scope_3_kg=scope_3_kg,
        co2_per_ton_km=co2_per_ton_km,
    )


@router.get("/flota", response_model=list[EcoFlotaSimRow])
async def flota_para_simulador(
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
    service: EcoService = Depends(deps.get_eco_service),
) -> list[EcoFlotaSimRow]:
    return await service.list_flota_simulador(empresa_id=current_user.empresa_id)


@router.get(
    "/certificate",
    summary="PDF profesional: emisiones mensuales CO2 por combustible (Scope 1)",
)
async def certificate_emisiones_mensuales(
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
    service: EcoService = Depends(deps.get_eco_service),
) -> StreamingResponse:
    """
    Certificado basado en gastos categoría COMBUSTIBLE de la empresa (JWT).
    Genera PDF vía `generar_pdf_certificado_emisiones_esg` en `pdf_service`.
    """
    eid = current_user.empresa_id
    meses = await service.emisiones_combustible_por_mes(empresa_id=eid)
    co2_tot, lit_tot = await service.co2_emisiones_combustible_scope1(empresa_id=eid)
    nombre = await service.nombre_empresa_publico(empresa_id=eid)

    meses_dicts: list[dict[str, Any]] = [m.model_dump() for m in meses]
    pdf_bytes = generar_pdf_certificado_emisiones_esg(
        empresa_nombre=nombre,
        empresa_id=eid,
        meses=meses_dicts,
        co2_combustible_total_kg=co2_tot,
        litros_estimados_total=lit_tot,
        kg_co2_por_litro=KG_CO2_POR_LITRO_DIESEL,
        eur_por_litro_ref=EUR_POR_LITRO_DIESEL_REF,
    )
    safe_name = f"Certificado_Emisiones_ESG_{eid[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/certificado-oficial", summary="Genera certificado ESG oficial (legacy)")
async def certificado_oficial(
    payload: EcoCertificadoIn,
    current_user: UserOut = Depends(deps.get_current_user),
    _esg: None = Depends(deps.check_quota_limit("esg")),
) -> StreamingResponse:
    pdf_bytes = generar_pdf_oficial(payload.model_dump())
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=Certificado_Sostenibilidad_{current_user.empresa_id}.pdf"
            )
        },
    )
