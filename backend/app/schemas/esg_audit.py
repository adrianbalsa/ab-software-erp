from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


CertificacionEmisiones = Literal["Euro V", "Euro VI", "Electrico", "Hibrido"]


class ESGAuditClienteItem(BaseModel):
    cliente_id: UUID
    cliente_nombre: str | None = None
    co2_kg: float = Field(..., ge=0)


class ESGAuditCertificacionPie(BaseModel):
    certificacion: CertificacionEmisiones
    co2_kg: float = Field(..., ge=0)
    porcentaje: float = Field(..., ge=0, le=100)


class ESGAuditOut(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    total_huella_carbono_kg: float = Field(..., ge=0)
    top_clientes: list[ESGAuditClienteItem]
    porcentaje_emisiones_euro_v: float = Field(
        ...,
        ge=0,
        le=100,
        description="% de la huella total atribuible a vehículos Euro V",
    )
    porcentaje_emisiones_euro_vi: float = Field(
        ...,
        ge=0,
        le=100,
        description="% de la huella total atribuible a vehículos Euro VI",
    )
    desglose_certificacion: list[ESGAuditCertificacionPie]
    insight_optimizacion: str
    escenario_optimizacion_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="% de portes Euro V considerados en el escenario de optimización",
    )
    co2_ahorro_escenario_kg: float = Field(..., ge=0)
