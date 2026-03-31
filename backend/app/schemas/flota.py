from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.vehiculo import NormativaEuro


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
CertificacionEmisiones = Literal["Euro V", "Euro VI", "Electrico", "Hibrido"]
EngineClass = Literal["EURO_VI", "EURO_V", "EURO_IV", "EURO_III", "EV"]
FuelType = Literal["DIESEL", "ELECTRIC", "HIBRIDO", "GASOLINA"]


class FlotaVehiculoIn(BaseModel):
    """
    Replica la estructura del editor de `views/flota_view.py`.
    """

    id: Optional[str] = None
    vehiculo: str = Field(..., min_length=1, max_length=255, description="Alias interno o marca/modelo del vehículo", examples=["Scania R500 Rojo"])
    matricula: str = Field(..., min_length=1, max_length=255, description="Matrícula oficial del vehículo (sin guiones ni espacios preferiblemente)", examples=["1234ABC"])
    precio_compra: float = Field(..., ge=0, description="Precio de adquisición en EUR para amortización", examples=[120000.0])
    km_actual: float = Field(..., ge=0, description="Kilometraje actual del odómetro", examples=[450000.5])
    estado: FlotaEstado
    tipo_motor: FlotaTipoMotor
    itv_vencimiento: Optional[date] = None
    seguro_vencimiento: Optional[date] = None
    fecha_itv: Optional[date] = None
    fecha_seguro: Optional[date] = None
    fecha_tacografo: Optional[date] = None
    km_proximo_servicio: Optional[float] = Field(
        default=None,
        ge=0,
        description="Km en el que toca revisión (legacy km_proximo_servicio)",
    )
    certificacion_emisiones: CertificacionEmisiones = Field(
        default="Euro VI",
        description="Norma de emisiones (ESG auditoría)",
    )
    normativa_euro: NormativaEuro = Field(
        default=NormativaEuro.EURO_VI,
        description="Normativa EURO aplicada al factor CO₂ kg/km del motor ESG (porte).",
    )
    engine_class: EngineClass = Field(
        default="EURO_VI",
        description="Clase de motor para factores dinámicos ESG (GLEC).",
    )
    fuel_type: FuelType = Field(
        default="DIESEL",
        description="Tipo de combustible para factores dinámicos ESG (GLEC).",
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


class FlotaEstadoActualPorteOut(BaseModel):
    id: str
    origin: str
    destination: str
    estimatedMargin: float


class FlotaEstadoActualPositionOut(BaseModel):
    lat: float
    lng: float


class FlotaEstadoActualOut(BaseModel):
    """Contrato exacto para `FleetMapTruck` en frontend."""

    id: str
    position: FlotaEstadoActualPositionOut
    porte: FlotaEstadoActualPorteOut


LiveTrackingEstado = Literal["Disponible", "En Ruta", "Taller"]


class FlotaLiveTrackingOut(BaseModel):
    """Posición GPS ligera + estado operativo para centro de mando (Traffic Manager)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    matricula: str
    estado: LiveTrackingEstado
    ultima_latitud: float | None = None
    ultima_longitud: float | None = None
    ultima_actualizacion_gps: datetime | None = None
    conductor_nombre: str | None = Field(
        default=None,
        description="Nombre visible del perfil asignado al vehículo (inventario flota), si existe.",
    )


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

