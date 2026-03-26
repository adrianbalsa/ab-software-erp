from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


MantenimientoUrgencia = Literal["CRITICO", "ADVERTENCIA", "OK"]
TramiteAdministrativo = Literal["ITV", "SEGURO", "TACOGRAFO"]


def clasificar_urgencia(desgaste: float) -> MantenimientoUrgencia:
    if desgaste > 0.95:
        return "CRITICO"
    if desgaste > 0.85:
        return "ADVERTENCIA"
    return "OK"


def clasificar_fecha_urgencia(days_left: int) -> MantenimientoUrgencia:
    """
    Días hasta el vencimiento (negativo = ya vencido).
    Umbrales alineados con alertas de calendario (ITV/seguro/tacógrafo).
    """
    if days_left < 0:
        return "CRITICO"
    if days_left <= 14:
        return "CRITICO"
    if days_left <= 45:
        return "ADVERTENCIA"
    return "OK"


class MantenimientoAlertaOut(BaseModel):
    origen: Literal["plan_km"] = Field(default="plan_km", description="Alerta por plan de mantenimiento por km")
    plan_id: UUID
    vehiculo_id: UUID
    matricula: str | None = None
    vehiculo: str | None = None
    tipo_tarea: str
    intervalo_km: int
    ultimo_km_realizado: int
    odometro_actual: int
    km_desde_ultimo: int
    desgaste: float = Field(description="(odometro_actual - ultimo_km_realizado) / intervalo_km")
    urgencia: MantenimientoUrgencia


class AlertaAdministrativaOut(BaseModel):
    """Vencimiento administrativo (ITV, seguro, tacógrafo) frente a hoy (UTC)."""

    origen: Literal["tramite_fecha"] = "tramite_fecha"
    vehiculo_id: UUID
    matricula: str | None = None
    vehiculo: str | None = None
    tipo_tramite: TramiteAdministrativo
    fecha_vencimiento: date
    dias_restantes: int = Field(description="Días hasta la fecha (negativo = vencido)")
    urgencia: MantenimientoUrgencia


class MantenimientoRegistrarIn(BaseModel):
    plan_id: UUID
    importe_eur: float = Field(gt=0, description="Importe del mantenimiento (gasto operativo)")
    proveedor: str = Field(default="Taller", min_length=1, max_length=255)
    concepto: str | None = Field(default=None, max_length=500)


class MantenimientoRegistrarOut(BaseModel):
    plan_id: UUID
    ultimo_km_realizado: int
    gasto_id: str
