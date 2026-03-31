from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class EcoCalculoIn(BaseModel):
    n_tickets: Annotated[int, Field(ge=0)] = 0
    tipos_motor: list[str] = Field(default_factory=list, description="Lista de motorizaciones de la flota")


class EcoSimuladorIn(BaseModel):
    """Payload mínimo para el simulador ESG (solo tickets + motorizaciones)."""

    n_tickets: Annotated[int, Field(ge=0)] = 0
    tipos_motor: list[str] = Field(default_factory=list, max_length=500)


class EcoResumenOut(BaseModel):
    n_tickets: int
    papel_kg: float
    co2_tickets: float
    co2_flota: float
    """CO2 Scope 1 estimado desde gastos categoría COMBUSTIBLE (diesel, kg)."""
    co2_combustible: float = 0.0
    co2_total: float
    flota_vehiculos: int


class EcoResumenLiteOut(BaseModel):
    """Respuesta compacta para GET /eco/resumen."""

    n_tickets: int
    papel_kg: float
    co2_tickets: float
    co2_flota: float
    co2_combustible: float = Field(
        0.0,
        description="CO2 Scope 1 (kg) desde gastos COMBUSTIBLE (factor diesel estándar)",
    )
    co2_total: float
    total_co2_kg: float = Field(..., ge=0, description="CO2 total (kg) con factores dinámicos por porte")
    scope_1_kg: float = Field(..., ge=0, description="Emisiones Scope 1 (flota propia)")
    scope_3_kg: float = Field(..., ge=0, description="Emisiones Scope 3 (subcontratado)")
    co2_per_ton_km: float = Field(..., ge=0, description="Intensidad: kg CO2 por ton·km")


class EcoFlotaSimRow(BaseModel):
    """Solo campos necesarios para el simulador (GET /eco/flota)."""

    id: str
    matricula: str
    motor: str = Field(..., description="Motorización (mapea tipo_motor en BD)")


class EcoCertificadoIn(BaseModel):
    """
    Inputs mínimos para el PDF del certificado oficial (legacy `views/eco_view.py`).
    """

    n_tickets: int
    papel_kg: float
    co2_total: float


class EcoEmisionMensualOut(BaseModel):
    """Un mes de emisiones por combustible (Scope 1)."""

    periodo: str = Field(..., description="YYYY-MM")
    co2_kg: float
    litros_estimados: float


class EcoDashboardOut(BaseModel):
    """Dashboard ESG: agregado de portes facturados en el mes calendario actual."""

    anio: int
    mes: int
    co2_kg_portes_facturados: float = Field(
        ...,
        description="Suma de co2_emitido (kg) de portes facturados en el mes",
    )
    num_portes_facturados: int
    scope_1_kg: float = Field(default=0.0, ge=0)
    scope_3_kg: float = Field(default=0.0, ge=0)
    co2_per_ton_km: float = Field(default=0.0, ge=0)
