"""Importación CSV de combustible (tarjetas tipo Solred / StarRessa) — gastos, ESG y odómetro."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.combustible_service import importar_combustible_csv
from app.services.gastos_service import GastosService

router = APIRouter()


class FuelImportacionResponse(BaseModel):
    total_filas_leidas: int = Field(..., ge=0)
    filas_importadas_ok: int = Field(..., ge=0)
    total_litros: float = Field(..., ge=0)
    total_euros: float = Field(..., ge=0)
    total_co2_kg: float = Field(..., ge=0)
    errores: list[str] = Field(default_factory=list)


@router.post(
    "/importar-combustible",
    response_model=FuelImportacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar CSV de combustible (ERP / tarjeta profesional)",
)
async def importar_combustible(
    file: UploadFile = File(...),
    _: UserOut = Depends(deps.RoleChecker(["admin", "gestor"])),
    current_user: UserOut = Depends(deps.bind_write_context),
    gastos_service: GastosService = Depends(deps.get_gastos_service),
    db: SupabaseAsync = Depends(deps.get_db),
) -> FuelImportacionResponse:
    """
    Columnas esperadas: **Fecha**, **Matricula**, **Litros**, **Importe_Total**;
    opcionales: **Proveedor**, **Kilometros** (odómetro; si supera ``flota.odometro_actual`` se actualiza).

    Crea filas en ``gastos`` (categoría Combustible), ``gastos_vehiculo`` y ``esg_auditoria``
    (CO₂ calculado por trigger según certificación del vehículo).
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Archivo sin nombre")

    raw = await file.read()
    try:
        out = await importar_combustible_csv(
            raw=raw,
            filename=file.filename or "import.csv",
            empresa_id=str(current_user.empresa_id),
            username_empleado=current_user.username,
            db=db,
            gastos_service=gastos_service,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    return FuelImportacionResponse(
        total_filas_leidas=out.total_filas_leidas,
        filas_importadas_ok=out.filas_importadas_ok,
        total_litros=out.total_litros,
        total_euros=out.total_euros,
        total_co2_kg=out.total_co2_kg,
        errores=out.errores,
    )
