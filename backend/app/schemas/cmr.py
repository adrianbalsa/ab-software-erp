"""Payload estructurado para Carta de Porte (CMR) — alineado a casillas habituales."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CmrPartyBlock(BaseModel):
    """Bloque de identificación (remitente, consignatario, transportista)."""

    nombre: str | None = None
    nif: str | None = None
    direccion: str | None = None
    pais: str | None = Field(default=None, description="País (opcional)")


class CmrLugarFecha(BaseModel):
    lugar: str | None = None
    fecha: date | None = None


class CmrMercanciaBlock(BaseModel):
    """Casillas 6–12 (naturaleza, embalaje, peso, volumen) — agregado operativo."""

    descripcion: str | None = None
    bultos: int | None = None
    peso_kg: float | None = Field(default=None, description="Peso bruto en kg si se conoce")
    peso_ton: float | None = Field(default=None, description="Toneladas informadas en porte")
    volumen_m3: float | None = None
    matricula_vehiculo: str | None = None
    nombre_vehiculo: str | None = Field(default=None, description="Denominación interna flota")
    nombre_conductor: str | None = None


class CmrDataOut(BaseModel):
    """Datos para rellenar plantilla CMR (firma 22–24 vacías en PDF)."""

    porte_id: UUID
    fecha: date
    km_estimados: float | None = None

    casilla_1_remitente: CmrPartyBlock = Field(
        ...,
        description="Remitente (por defecto datos del cliente cargador)",
    )
    casilla_2_consignatario: CmrPartyBlock = Field(
        ...,
        description="Consignatario en destino; si no hay datos separados, solo dirección/destino",
    )
    casilla_3_lugar_entrega_mercancia: str | None = Field(
        default=None,
        description="Lugar previsto de entrega (p. ej. destino)",
    )
    casilla_4_lugar_fecha_toma_carga: CmrLugarFecha = Field(
        ...,
        description="Lugar y fecha de toma de la mercancía",
    )
    casilla_6_12_mercancia: CmrMercanciaBlock
    casilla_16_transportista: CmrPartyBlock = Field(
        ...,
        description="Transportista (empresa)",
    )

    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Campos extra para la UI (p. ej. etiquetas de casilla)",
    )
