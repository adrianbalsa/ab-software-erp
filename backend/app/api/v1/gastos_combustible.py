"""Importación CSV de combustible (tarjetas tipo Solred / StarRessa) — gastos, ESG y odómetro."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.api import deps
from app.api.auth_token import get_access_token
from app.core.import_telemetry import log_import_event
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.combustible_service import FuelImportErrorDetail, importar_combustible_csv
from app.services.fuel_import_jobs import create_fuel_import_job, get_fuel_import_job, run_fuel_import_job
from app.services.gastos_service import GastosService

router = APIRouter()


class FuelImportErrorItem(BaseModel):
    row: int | None = Field(default=None, description="Índice 1..N en el lote tras filtros de cabecera.")
    code: str
    message: str


class FuelImportacionResponse(BaseModel):
    total_filas_leidas: int = Field(..., ge=0)
    filas_importadas_ok: int = Field(..., ge=0)
    total_litros: float = Field(..., ge=0)
    total_euros: float = Field(..., ge=0)
    total_co2_kg: float = Field(..., ge=0)
    errores: list[str] = Field(default_factory=list)
    solo_validacion: bool = Field(
        default=False,
        description="True si la respuesta es simulación (sin escritura en base de datos).",
    )
    errores_detalle: list[FuelImportErrorItem] = Field(default_factory=list)
    co2_es_estimacion: bool = Field(
        default=False,
        description="True si el CO₂ agregado es estimación ISO 14083 (solo en validación).",
    )


class FuelImportJobQueuedOut(BaseModel):
    job_id: str
    status: str = "queued"
    poll_path: str


class FuelImportJobStatusOut(BaseModel):
    job_id: str
    status: str
    progress: int = Field(..., ge=0, le=100)
    result: FuelImportacionResponse | None = None
    error: str | None = None


def _fuel_response_payload(out: object) -> FuelImportacionResponse:
    """Convierte ``FuelImportResult`` (dataclass) a modelo API."""
    dry_run = bool(getattr(out, "dry_run", False))
    det_raw: list[FuelImportErrorDetail] = list(getattr(out, "errores_detalle", []) or [])
    det = [FuelImportErrorItem(row=d.row, code=d.code, message=d.message) for d in det_raw]
    return FuelImportacionResponse(
        total_filas_leidas=int(getattr(out, "total_filas_leidas")),
        filas_importadas_ok=int(getattr(out, "filas_importadas_ok")),
        total_litros=float(getattr(out, "total_litros")),
        total_euros=float(getattr(out, "total_euros")),
        total_co2_kg=float(getattr(out, "total_co2_kg")),
        errores=list(getattr(out, "errores")),
        solo_validacion=dry_run,
        errores_detalle=det,
        co2_es_estimacion=bool(getattr(out, "co2_es_estimacion", False)),
    )


def _fuel_result_dict_to_response(data: dict) -> FuelImportacionResponse:
    """Reconstruye respuesta desde ``asdict(FuelImportResult)`` (jobs async)."""
    det_raw = data.get("errores_detalle") or []
    det: list[FuelImportErrorItem] = []
    for d in det_raw:
        if isinstance(d, dict):
            det.append(FuelImportErrorItem(row=d.get("row"), code=str(d.get("code", "")), message=str(d.get("message", ""))))
    return FuelImportacionResponse(
        total_filas_leidas=int(data["total_filas_leidas"]),
        filas_importadas_ok=int(data["filas_importadas_ok"]),
        total_litros=float(data["total_litros"]),
        total_euros=float(data["total_euros"]),
        total_co2_kg=float(data["total_co2_kg"]),
        errores=list(data.get("errores") or []),
        solo_validacion=bool(data.get("dry_run", False)),
        errores_detalle=det,
        co2_es_estimacion=bool(data.get("co2_es_estimacion", False)),
    )


@router.post(
    "/importar-combustible",
    response_model=FuelImportacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar CSV de combustible (ERP / tarjeta profesional)",
)
async def importar_combustible(
    request: Request,
    file: UploadFile = File(...),
    current_user: UserOut = Depends(deps.require_write_role("owner", "traffic_manager")),
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
    log_import_event(
        request,
        "fuel_csv_import_sync_started",
        empresa_id=str(current_user.empresa_id),
        extra={"bytes": len(raw)},
    )
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

    resp = _fuel_response_payload(out)
    log_import_event(
        request,
        "fuel_csv_import_sync_completed",
        empresa_id=str(current_user.empresa_id),
        extra={
            "filas_ok": resp.filas_importadas_ok,
            "filas_tot": resp.total_filas_leidas,
            "errores": len(resp.errores),
        },
    )
    return resp


@router.post(
    "/validar-importacion-combustible",
    response_model=FuelImportacionResponse,
    status_code=status.HTTP_200_OK,
    summary="Validar CSV de combustible (sin persistir)",
)
async def validar_importacion_combustible(
    request: Request,
    file: UploadFile = File(...),
    current_user: UserOut = Depends(deps.require_write_role("owner", "traffic_manager")),
    gastos_service: GastosService = Depends(deps.get_gastos_service),
    db: SupabaseAsync = Depends(deps.get_db),
) -> FuelImportacionResponse:
    """
    Misma lógica de análisis que ``importar-combustible`` pero **sin** crear gastos ni ESG.
    El CO₂ devuelto es **estimación** normativa (kg/L ISO 14083); el import real usa el trigger de BD.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Archivo sin nombre")

    raw = await file.read()
    log_import_event(
        request,
        "fuel_csv_validate_started",
        empresa_id=str(current_user.empresa_id),
        extra={"bytes": len(raw)},
    )
    try:
        out = await importar_combustible_csv(
            raw=raw,
            filename=file.filename or "import.csv",
            empresa_id=str(current_user.empresa_id),
            username_empleado=current_user.username,
            db=db,
            gastos_service=gastos_service,
            dry_run=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    resp = _fuel_response_payload(out)
    log_import_event(
        request,
        "fuel_csv_validate_completed",
        empresa_id=str(current_user.empresa_id),
        extra={
            "filas_ok": resp.filas_importadas_ok,
            "filas_tot": resp.total_filas_leidas,
            "errores": len(resp.errores),
        },
    )
    return resp


@router.post(
    "/importar-combustible/jobs",
    response_model=FuelImportJobQueuedOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar importación CSV de combustible (seguimiento por progreso)",
)
async def enqueue_importar_combustible(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: UserOut = Depends(deps.require_write_role("owner", "traffic_manager")),
    token: str = Depends(get_access_token),
) -> FuelImportJobQueuedOut:
    """
    Acepta el archivo y procesa la importación **tras** enviar la respuesta HTTP.

    Pensado para CSV grandes: el cliente hace polling a ``GET …/jobs/{job_id}`` hasta ``completed``.
    Los bytes se retienen en memoria del proceso (TTL ~30 min); en multi-réplica usar cola compartida.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Archivo sin nombre")
    raw = await file.read()
    log_import_event(
        request,
        "fuel_csv_import_job_enqueued",
        empresa_id=str(current_user.empresa_id),
        extra={"bytes": len(raw)},
    )
    try:
        job_id = await create_fuel_import_job(
            empresa_id=str(current_user.empresa_id),
            username_empleado=current_user.username,
            access_token=token,
            raw=raw,
            filename=file.filename or "import.csv",
        )
    except ValueError as e:
        msg = str(e)
        if "demasiado grande" in msg.lower():
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg) from e

    background_tasks.add_task(run_fuel_import_job, job_id)
    return FuelImportJobQueuedOut(
        job_id=job_id,
        poll_path=f"/api/v1/gastos/importar-combustible/jobs/{job_id}",
    )


@router.get(
    "/importar-combustible/jobs/{job_id}",
    response_model=FuelImportJobStatusOut,
    summary="Estado de importación combustible encolada",
)
async def get_importar_combustible_job(
    job_id: str,
    current_user: UserOut = Depends(deps.require_write_role("owner", "traffic_manager")),
) -> FuelImportJobStatusOut:
    row = await get_fuel_import_job(job_id=job_id, empresa_id=str(current_user.empresa_id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
    result = None
    raw_res = row.get("result")
    if isinstance(raw_res, dict):
        result = _fuel_result_dict_to_response(raw_res)
    return FuelImportJobStatusOut(
        job_id=str(row["job_id"]),
        status=str(row["status"]),
        progress=int(row.get("progress") or 0),
        result=result,
        error=row.get("error"),
    )
