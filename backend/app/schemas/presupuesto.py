from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class PresupuestoMaterialLineaIn(BaseModel):
    descripcion: str | None = None
    cantidad: Annotated[float, Field(ge=0)] = 0.0
    precio: Annotated[float, Field(ge=0)] = 0.0


class PresupuestoVerifactuIn(BaseModel):
    nif_empresa: str = Field(..., min_length=1)
    nif_cliente: str = Field(..., min_length=1)
    num_documento: str = Field(..., min_length=1, description="Identificador del documento (presupuesto/factura)")
    fecha: str = Field(..., min_length=1, description="ISO date string (YYYY-MM-DD)")
    hash_anterior: str | None = None


class PresupuestoCalculoIn(BaseModel):
    # Obra
    metros_obra: Annotated[float, Field(ge=0)] = 0.0
    precio_m2: Annotated[float, Field(ge=0)] = 0.0

    # Mano de obra
    num_trabajadores: Annotated[int, Field(ge=0)] = 0
    horas_por_trab: Annotated[float, Field(ge=0)] = 0.0
    coste_hora: Annotated[float, Field(ge=0)] = 0.0

    # Materiales
    materiales: list[PresupuestoMaterialLineaIn] = Field(default_factory=list)

    # Totalización
    margen_pct: Annotated[float, Field(ge=0, le=100)] = 15.0
    iva_pct: Annotated[float, Field(ge=0, le=100)] = 21.0

    # Extra (opcional)
    moneda: str | None = "EUR"
    verifactu: PresupuestoVerifactuIn | None = None


class PresupuestoLineaOut(BaseModel):
    concepto: str
    cantidad: float
    precio_unitario: float
    total: float


class PresupuestoCalculoOut(BaseModel):
    subtotal_obra: float
    subtotal_mo: float
    subtotal_materiales: float

    subtotal_obra_final: float
    subtotal_mo_final: float
    subtotal_materiales_final: float

    subtotal_final: float
    cuota_iva: float
    total_final: float

    items: list[PresupuestoLineaOut]
    moneda: str | None = None

    # Encadenado (hash determinista)
    hash_documento: str | None = None
