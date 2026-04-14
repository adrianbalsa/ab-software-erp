from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_serializer

from app.core.math_engine import as_float_fiat
from app.models.invoice import PaymentStatus
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

    cliente_id: UUID = Field(..., description="ID del cliente/cargador (FK clientes)", examples=["123e4567-e89b-12d3-a456-426614174000"])
    iva_porcentaje: Annotated[float, Field(ge=0, le=100, description="Porcentaje de IVA a aplicar", examples=[21.0])] = 21.0
    porte_ids: list[UUID] | None = Field(
        default=None,
        description="Opcional: subconjunto de IDs de portes pendientes a incluir en la factura",
        examples=[["123e4567-e89b-12d3-a456-426614174001"]]
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
    huella_hash: str | None = Field(
        default=None,
        description="Huella SHA-256 encadenada persistida para VeriFactu (alias de hash_registro).",
    )
    huella_anterior: str | None = Field(
        default=None,
        description="Huella previa en la cadena VeriFactu para esta factura.",
    )
    fecha_hitos_verifactu: datetime | None = Field(
        default=None,
        description="Timestamp del hito de sellado/encadenado VeriFactu.",
    )
    bloqueado: bool | None = None
    fingerprint: str | None = Field(
        default=None,
        description="Huella encadenada VeriFactu (post-finalización); puede diferir de hash_registro",
    )
    fingerprint_hash: str | None = Field(
        default=None,
        description="Hash de encadenamiento de factura (integridad inmutable por registro).",
    )
    prev_fingerprint: str | None = Field(
        default=None,
        description="Huella fingerprint de la factura finalizada anterior en la cadena",
    )
    previous_fingerprint: str | None = Field(
        default=None,
        description="Hash de la factura anterior en la cadena de fingerprint_hash.",
    )
    previous_invoice_hash: str | None = Field(
        default=None,
        description="Hash SHA-256 de la factura anterior en la cadena VeriFactu (Ley Antifraude).",
    )
    qr_code_url: str | None = Field(
        default=None,
        description="URL TIKE de cotejo AEAT codificada en el QR de registro",
    )
    qr_content: str | None = Field(
        default=None,
        description="Contenido literal de la URL codificada en el QR VeriFactu.",
    )
    is_finalized: bool | None = Field(
        default=None,
        description="TRUE cuando se completó POST finalizar (QR + cadena fingerprint)",
    )
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
    payment_status: PaymentStatus = Field(
        default=PaymentStatus.PENDING,
        description="Estado de pago normalizado para integración bancaria (PENDING | PAID | OVERDUE)",
    )
    aeat_sif_estado: str | None = Field(
        default=None,
        description="Estado remisión SIF AEAT: aceptado, aceptado_con_errores, rechazado, error_tecnico, omitido, pendiente",
    )
    aeat_sif_csv: str | None = Field(default=None, description="CSV o traza devuelta por la AEAT")
    aeat_sif_codigo: str | None = Field(default=None)
    aeat_sif_descripcion: str | None = Field(default=None)
    aeat_sif_actualizado_en: datetime | None = Field(default=None)

    model_config = ConfigDict(extra="ignore")

    @field_serializer("base_imponible", "cuota_iva", "total_factura", mode="plain")
    def _ser_fiat_amounts(self, v: float) -> float:
        return as_float_fiat(v)

    @field_serializer("total_km_estimados_snapshot", mode="plain")
    def _ser_km_snapshot(self, v: float | None) -> float | None:
        if v is None:
            return None
        return as_float_fiat(v)


class FacturaGenerateResult(BaseModel):
    factura: FacturaOut
    portes_facturados: list[UUID]
    pdf_base64: str | None = None
    pdf_storage_path: str | None = None


class FacturaRecalculateIn(BaseModel):
    """Opciones para recalcular totales desde el snapshot (sin persistir si no se indica)."""

    global_discount: float = Field(default=0, ge=0, description="Descuento global en EUR")
    aplicar_recargo_equivalencia: bool = False


class FacturaRecalculateOut(BaseModel):
    """Desglose MathEngine (ROUND_HALF_EVEN a céntimo, coherente con ``math_engine``)."""

    factura_id: int
    base_imponible: float
    cuota_iva: float
    cuota_recargo_equivalencia: float
    total_factura: float
    desglose_por_tipo: list[dict[str, Any]]
    lineas: list[dict[str, Any]]
    ajuste_centimos: float
    importe_descuento_global_aplicado: float

    @field_serializer(
        "base_imponible",
        "cuota_iva",
        "cuota_recargo_equivalencia",
        "total_factura",
        "ajuste_centimos",
        "importe_descuento_global_aplicado",
        mode="plain",
    )
    def _ser_recalc(self, v: float) -> float:
        return as_float_fiat(v)


class FacturaPdfEmisorOut(BaseModel):
    """Emisor fiscal para plantilla PDF comercial."""

    nombre: str
    nif: str
    direccion: str | None = None


class FacturaPdfReceptorOut(BaseModel):
    nombre: str
    nif: str | None = None


class FacturaPdfLineaOut(BaseModel):
    concepto: str
    cantidad: float
    precio_unitario: float
    importe: float

    @field_serializer("cantidad", "precio_unitario", "importe", mode="plain")
    def _ser_linea_qty(self, v: float) -> float:
        return as_float_fiat(v)


class FacturaPdfDataOut(BaseModel):
    """
    Payload para ``@react-pdf/renderer``: totales redondeados con el Math Engine,
    QR VeriFactu (TIKE) en Base64 y metadatos de auditoría.
    """

    factura_id: int
    numero_factura: str
    num_factura_verifactu: str | None = None
    tipo_factura: str | None = None
    fecha_emision: date
    emisor: FacturaPdfEmisorOut
    receptor: FacturaPdfReceptorOut
    lineas: list[FacturaPdfLineaOut]
    base_imponible: float
    tipo_iva_porcentaje: float
    cuota_iva: float
    total_factura: float
    verifactu_qr_base64: str = Field(
        default="",
        description="PNG del QR en Base64 (ASCII); vacío si no hay URL TIKE válida.",
    )
    verifactu_validation_url: str | None = Field(
        default=None,
        description="URL codificada en el QR (TIKE o reconstruida).",
    )
    verifactu_hash_audit: str = Field(
        default="",
        description="Primeros y últimos 8 caracteres del fingerprint o hash_registro para pie legal.",
    )
    fingerprint_completo: str | None = Field(
        default=None,
        description="Huella encadenada VeriFactu si la factura está finalizada.",
    )
    hash_registro: str | None = None
    aeat_csv_ultimo_envio: str | None = Field(
        default=None,
        description="CSV/traza del último registro en ``verifactu_envios`` (si existe).",
    )
    esg_portes_count: int | None = Field(
        default=None,
        description="Número de portes vinculados a la factura para agregado ESG.",
    )
    esg_total_km: float | None = Field(
        default=None,
        description="Suma km estimados de portes facturados (distancia operativa declarada).",
    )
    esg_total_co2_kg: float | None = Field(
        default=None,
        description="Suma CO₂ kg (GLEC ``calculate_co2_footprint`` por porte).",
    )
    esg_euro_iii_baseline_kg: float | None = Field(
        default=None,
        description="Suma línea base Euro III (mismo recorrido por porte).",
    )
    esg_ahorro_vs_euro_iii_kg: float | None = Field(
        default=None,
        description="Ahorro total kg CO₂ vs Euro III (agregado factura).",
    )

    @field_serializer(
        "base_imponible",
        "tipo_iva_porcentaje",
        "cuota_iva",
        "total_factura",
        "esg_total_km",
        "esg_total_co2_kg",
        "esg_euro_iii_baseline_kg",
        "esg_ahorro_vs_euro_iii_kg",
        mode="plain",
    )
    def _ser_pdf_totals(self, v: float) -> float:
        return as_float_fiat(v)


class FacturaEmailEnviadaOut(BaseModel):
    """Respuesta tras enviar la factura por SMTP (auditoría de envío)."""

    factura_id: int
    numero_factura: str
    destinatario: str = Field(..., description="Correo del cliente al que se envió el PDF")
    enviado_en: datetime = Field(..., description="Marca temporal UTC del envío")
    mensaje: str = Field(default="Factura enviada por correo correctamente.")
    auditoria: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos de trazabilidad (acción, canal, registro)",
    )
