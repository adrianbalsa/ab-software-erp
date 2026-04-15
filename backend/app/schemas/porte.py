from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.math_engine import as_float_fiat
from app.schemas.cliente import ClienteOut


PorteEstado = Literal["pendiente", "Entregado", "facturado"]


class PorteCreate(BaseModel):
    cliente_id: UUID = Field(..., description="ID del cliente/cargador (FK clientes)", examples=["123e4567-e89b-12d3-a456-426614174000"])
    fecha: date = Field(..., description="Fecha programada de servicio", examples=["2026-04-15"])
    origen: str = Field(..., min_length=1, max_length=255, description="Dirección de carga", examples=["Madrid, Centro Logístico Sur"])
    destino: str = Field(..., min_length=1, max_length=255, description="Dirección de descarga", examples=["Barcelona, Polígono Zona Franca"])
    km_estimados: float = Field(default=0.0, ge=0, description="Distancia estimada en kilómetros", examples=[620.5])
    km_vacio: float = Field(
        default=0.0,
        ge=0,
        description="Kilómetros en vacío (sin carga) para cálculo dinámico de CO2.",
        examples=[120.0],
    )
    bultos: int = Field(default=1, ge=1, description="Número de bultos o palets", examples=[33])
    peso_ton: float | None = Field(
        default=None,
        ge=0,
        description="Peso de carga en toneladas (ESG); si no se envía, se estima desde bultos",
        examples=[24.0]
    )
    descripcion: str | None = Field(default=None, max_length=500, description="Observaciones del porte", examples=["Carga paletizada refrigerada"])
    precio_pactado: float = Field(..., gt=0, description="Precio pactado en EUR (sin impuestos)", examples=[1250.0])
    vehiculo_id: UUID | None = Field(
        default=None,
        description="Vehículo de flota (public.flota.id) asignado al porte; determina normativa EURO del CO₂.",
        examples=["456e4567-e89b-12d3-a456-426614174001"]
    )
    subcontratado: bool = Field(
        default=False,
        description="True si el porte es subcontratado (Scope 3), False para flota propia (Scope 1).",
    )


class PorteOut(BaseModel):
    """Porte con FKs UUID; `cliente_detalle` opcional para respuestas enriquecidas."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    empresa_id: UUID
    cliente_id: UUID | None = Field(
        default=None,
        description="Oculto (null) en API para rol driver.",
    )
    fecha: date
    origen: str
    destino: str
    km_estimados: float
    km_vacio: float | None = Field(
        default=None,
        description="Kilómetros en vacío del porte.",
    )
    bultos: int
    descripcion: str | None
    precio_pactado: float | None = Field(
        default=None,
        description="Oculto (null) en API para rol driver.",
    )
    vehiculo_id: UUID | None = Field(
        default=None,
        description="Vehículo de flota asignado (public.flota.id).",
    )
    co2_emitido: float | None = Field(
        default=None,
        description="kg CO2 estimados (Enterprise; distancia × toneladas × factor)",
    )
    peso_ton: float | None = Field(
        default=None,
        description="Toneladas de carga informadas (opcional)",
    )
    estado: PorteEstado
    subcontratado: bool = Field(
        default=False,
        description="Porte subcontratado (Scope 3).",
    )
    factura_id: int | None = None
    co2_kg: float | None = Field(
        default=None,
        description="kg CO₂ (norma EURO km) persistido en BD; ver ``calculate_co2_emissions``.",
    )
    vehiculo_matricula: str | None = Field(
        default=None,
        description="Matrícula del vehículo de flota asignado (enriquecido en GET detalle).",
    )
    vehiculo_modelo: str | None = Field(
        default=None,
        description="Denominación del vehículo en inventario flota.",
    )
    vehiculo_normativa_euro: str | None = Field(
        default=None,
        description="Normativa EURO resuelta para reporting CO₂ (p. ej. Euro VI).",
    )
    vehiculo_engine_class: str | None = Field(
        default=None,
        description="Clase motor GLEC (p. ej. EURO_VI) desde flota.",
    )
    vehiculo_fuel_type: str | None = Field(
        default=None,
        description="Tipo de combustible GLEC (p. ej. DIESEL) desde flota.",
    )
    esg_co2_total_kg: float | None = Field(
        default=None,
        description="CO₂ total kg (motor GLEC cargado/vacío; ``calculate_co2_footprint``).",
    )
    esg_co2_euro_iii_baseline_kg: float | None = Field(
        default=None,
        description="Mismo recorrido con motor Euro III (línea base certificado).",
    )
    esg_co2_ahorro_vs_euro_iii_kg: float | None = Field(
        default=None,
        description="Ahorro kg CO₂ vs línea base Euro III (≥ 0).",
    )
    lat_origin: float | None = Field(
        default=None,
        description="Latitud geocodificada del origen (Google Geocoding).",
    )
    lng_origin: float | None = Field(
        default=None,
        description="Longitud geocodificada del origen.",
    )
    lat_dest: float | None = Field(
        default=None,
        description="Latitud geocodificada del destino.",
    )
    lng_dest: float | None = Field(
        default=None,
        description="Longitud geocodificada del destino.",
    )
    real_distance_meters: float | None = Field(
        default=None,
        description="Distancia carretera en metros (Routes API) para CO₂ / reporting.",
    )
    nombre_consignatario_final: str | None = Field(
        default=None,
        description="Nombre quien firma la entrega (POD).",
    )
    fecha_entrega_real: datetime | None = Field(
        default=None,
        description="Marca hora de entrega confirmada.",
    )
    deleted_at: datetime | None = None
    cliente_detalle: ClienteOut | None = Field(
        default=None,
        description="Opcional: maestro cliente (no viene de PostgREST en el SELECT * estándar)",
    )

    @field_serializer(
        "km_estimados",
        "precio_pactado",
        "co2_emitido",
        "co2_kg",
        "peso_ton",
        "esg_co2_total_kg",
        "esg_co2_euro_iii_baseline_kg",
        "esg_co2_ahorro_vs_euro_iii_kg",
        "lat_origin",
        "lng_origin",
        "lat_dest",
        "lng_dest",
        "real_distance_meters",
        mode="plain",
    )
    def _ser_porte_qty(self, v: float | None) -> float | None:
        if v is None:
            return None
        return as_float_fiat(v)


class FirmaEntregaIn(BaseModel):
    """Firma digital del consignatario (canvas PNG en Base64)."""

    firma_b64: str = Field(..., min_length=10, max_length=2_500_000)
    nombre_consignatario: str = Field(..., min_length=1, max_length=255)
    dni_consignatario: str | None = Field(
        default=None,
        max_length=32,
        description="DNI/NIE del receptor (opcional).",
    )


class FirmaEntregaOut(BaseModel):
    porte_id: UUID
    estado: str
    fecha_entrega_real: datetime
    odometro_actualizado: bool = False
    odometro_error: str | None = None


class PorteCotizarIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    origen: str = Field(..., min_length=1, max_length=255)
    destino: str = Field(..., min_length=1, max_length=255)
    km_estimados: float | None = Field(
        default=None,
        ge=0,
        description="Si se omite o es 0, se calculan km con Google Directions (ruta óptima + tráfico).",
    )
    waypoints: list[str] | None = Field(
        default=None,
        description="Paradas intermedias opcionales (direcciones) para Directions API.",
    )
    precio_oferta: float = Field(
        default=0.0,
        ge=0,
        description="Precio ofertado para el servicio (sin IVA, coherente con coste operativo estimado).",
    )
    empresa_id: UUID | None = Field(
        default=None,
        description="Opcional; informativo desde el cliente. El tenant efectivo es el del JWT.",
    )


class PorteCotizarOut(BaseModel):
    kilometros_totales: float
    tiempo_estimado_min: int
    coste_operativo_estimado: float
    margen_proyectado: float | None = Field(
        default=None,
        description="Null para rol traffic_manager (no visibilidad de margen proyectado).",
    )
    es_rentable: bool | None = Field(
        default=None,
        description="True si precio_oferta > coste_operativo; null si no se indicó precio.",
    )
    tiene_peajes: bool | None = Field(
        default=None,
        description="Solo si los km salieron de Google Directions (detección por ruta con peajes).",
    )
    precio_sugerido: float | None = Field(
        default=None,
        description="Coste operativo + margen proyectado (sin IVA) cuando no hay precio_oferta.",
    )
    distancia_desde_google_directions: bool = Field(
        default=False,
        description="True si los kilómetros se obtuvieron de la API Directions (no eran manuales).",
    )

    @field_serializer(
        "kilometros_totales",
        "coste_operativo_estimado",
        "margen_proyectado",
        "precio_sugerido",
        mode="plain",
    )
    def _ser_cotizar_fiat(self, v: float | None) -> float | None:
        if v is None:
            return None
        return as_float_fiat(v)
