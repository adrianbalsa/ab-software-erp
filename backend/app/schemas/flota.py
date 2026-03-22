from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AmortizacionLinealIn(BaseModel):
    valor_inicial: Annotated[float, Field(ge=0)] = 0.0
    vida_util_anios: Annotated[int, Field(ge=1)] = 5
    valor_residual: Annotated[float, Field(ge=0)] = 0.0


class AmortizacionLineaOut(BaseModel):
    anio: int
    cuota_anual: float
    amort_acumulada: float
    valor_neto_contable: float


class AmortizacionLinealOut(BaseModel):
    valor_inicial: float
    vida_util_anios: int
    valor_residual: float
    base_amortizable: float
    cuota_anual: float
    cuadro: list[AmortizacionLineaOut]
    serie_temporal: list[AmortizacionLineaOut] = Field(
        default_factory=list,
        description="Curva año a año (depreciación / VNC)",
    )


FlotaEstado = Literal["Operativo", "En Taller", "Baja", "Vendido"]
FlotaTipoMotor = Literal["Diesel", "Gasolina", "Híbrido", "Eléctrico"]


class FlotaVehiculoIn(BaseModel):
    """
    Replica la estructura del editor de `views/flota_view.py`.
    """

    id: Optional[str] = None
    vehiculo: str = Field(..., min_length=1, max_length=255)
    matricula: str = Field(..., min_length=1, max_length=255)
    precio_compra: float = Field(..., ge=0)
    km_actual: float = Field(..., ge=0)
    estado: FlotaEstado
    tipo_motor: FlotaTipoMotor
    itv_vencimiento: Optional[date] = None
    seguro_vencimiento: Optional[date] = None
    km_proximo_servicio: Optional[float] = Field(
        default=None,
        ge=0,
        description="Km en el que toca revisión (legacy km_proximo_servicio)",
    )


class FlotaVehiculoOut(FlotaVehiculoIn):
    id: str
    empresa_id: UUID
    deleted_at: datetime | None = None

    model_config = ConfigDict(extra="ignore")


FlotaAlertaTipo = Literal["itv_vencimiento", "seguro_vencimiento", "proxima_revision_km"]
FlotaAlertaPrioridad = Literal["alta", "media", "baja"]


class FlotaAlertaOut(BaseModel):
    """Alerta de mantenimiento / cumplimiento para dashboard y flota. [cite: 2026-03-22]"""

    tipo: FlotaAlertaTipo
    vehiculo_id: str
    matricula: str | None = None
    vehiculo: str | None = None
    prioridad: FlotaAlertaPrioridad
    detalle: str
    fecha_referencia: date | None = None
    km_restantes: float | None = None


class FlotaMetricasOut(BaseModel):
    """Resumen para gráficos (disponible vs riesgo de parada)."""

    total_vehiculos: int
    en_riesgo_parada: int
    disponibles: int
    pct_disponible: float
    pct_riesgo_parada: float


MantenimientoTipo = Literal[
    "Mecánica General",
    "Carrocería",
    "Neumáticos",
    "Electrónica",
    "ITV",
]


class MantenimientoFlotaCreate(BaseModel):
    """
    Replica el formulario de `views/flota_view.py` -> `mantenimiento_flota`.
    """

    vehiculo: str = Field(..., min_length=1, max_length=255)  # En legacy se guarda la matrícula
    fecha: date
    tipo: MantenimientoTipo
    coste: float = Field(..., ge=0)
    kilometros: float = Field(..., ge=0)
    descripcion: str | None = Field(default=None, max_length=2000)

