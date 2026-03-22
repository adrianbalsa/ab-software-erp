from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.cliente import ClienteOut


class FacturaRectificarIn(BaseModel):
    """Cuerpo para emitir factura rectificativa R1 sobre una F1 sellada."""

    motivo: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Motivo de la rectificación (expediente / VeriFactu)",
    )


class FacturaCreateFromPortes(BaseModel):
    """
    Create an invoice from all pending portes for a given client.
    Mirrors current Streamlit behavior (batch invoice per client).

    Si ``porte_ids`` se envía (no vacío), solo se facturan esos portes (deben estar
    pendientes y pertenecer al ``cliente_id`` indicado).
    """

    cliente_id: UUID = Field(..., description="ID del cliente/cargador (FK clientes)")
    iva_porcentaje: Annotated[float, Field(ge=0, le=100)] = 21.0
    porte_ids: list[UUID] | None = Field(
        default=None,
        description="Opcional: subconjunto de IDs de portes pendientes a incluir en la factura",
    )


class FacturaOut(BaseModel):
    id: int
    empresa_id: UUID
    cliente_id: UUID = Field(
        validation_alias=AliasChoices("cliente", "cliente_id"),
        description="FK a clientes.id (columna histórica `cliente` en `facturas`)",
    )
    cliente_detalle: ClienteOut | None = Field(
        default=None,
        description="Opcional: maestro `clientes` para UI (nombre, NIF, …)",
    )
    numero_factura: str = Field(
        ...,
        description="Número legible de factura (legacy); suele coincidir con `num_factura` VeriFactu",
    )
    fecha_emision: date
    base_imponible: float
    cuota_iva: float
    total_factura: float

    # VeriFactu / SIF (normativa española)
    tipo_factura: str | None = Field(
        default=None,
        description="Tipo de factura (p. ej. F1 factura completa)",
    )
    num_factura: str | None = Field(
        default=None,
        description="Serie-Año-Secuencial (identificador VeriFactu)",
    )
    nif_emisor: str | None = Field(
        default=None,
        description="NIF del obligado tributario (empresa), desde tabla empresas",
    )
    hash_registro: str | None = Field(
        default=None,
        description="SHA-256 huella del registro (encadenamiento)",
    )
    numero_secuencial: int | None = None
    hash_factura: str | None = Field(
        default=None,
        description="Alias histórico del hash de registro (mismo valor que hash_registro si aplica)",
    )
    hash_anterior: str | None = None
    bloqueado: bool | None = None
    xml_verifactu: str | None = Field(
        default=None,
        description="XML de alta VeriFactu (UTF-8) generado al emitir y sellar el hash",
    )

    # Congelado al emitir desde portes (no se recalcula si cambia el porte)
    porte_lineas_snapshot: list[dict[str, Any]] | None = Field(
        default=None,
        description="Líneas con precio_pactado y km_estimados al momento de la emisión",
    )
    total_km_estimados_snapshot: float | None = Field(
        default=None,
        description="Suma de km_estimados de las líneas facturadas (estático)",
    )
    factura_rectificada_id: int | None = Field(
        default=None,
        description="PK (BIGINT) de la factura original (F1) que corrige esta R1",
    )
    motivo_rectificacion: Optional[str] = Field(
        default=None,
        description="Texto del motivo de rectificación",
    )
    estado_cobro: str | None = Field(
        default=None,
        description="emitida | cobrada (conciliación bancaria)",
    )
    pago_id: str | None = Field(
        default=None,
        description="Identificador del movimiento bancario emparejado (GoCardless / ref.)",
    )

    model_config = ConfigDict(extra="ignore")


class FacturaGenerateResult(BaseModel):
    factura: FacturaOut
    portes_facturados: list[UUID]
    pdf_base64: str | None = None
    pdf_storage_path: str | None = None
