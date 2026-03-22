from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.api import deps
from app.schemas.gasto import GastoCreate, GastoOCRHint, GastoOut
from app.schemas.user import UserOut
from app.services.gastos_service import GastosService


router = APIRouter()


def _parse_fecha(raw: str) -> date:
    try:
        return date.fromisoformat(raw.strip()[:10])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"fecha inválida (use YYYY-MM-DD): {e}") from e


def _optional_float(name: str, raw: str | None) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{name} debe ser numérico") from e


@router.get("/", response_model=list[GastoOut])
async def list_gastos(
    current_user: UserOut = Depends(deps.get_current_user),
    service: GastosService = Depends(deps.get_gastos_service),
) -> list[GastoOut]:
    return await service.list_gastos(empresa_id=current_user.empresa_id)


@router.post("/", response_model=GastoOut, status_code=status.HTTP_201_CREATED)
async def create_gasto(
    proveedor: str = Form(...),
    fecha: str = Form(...),
    total_chf: float = Form(...),
    categoria: str = Form(...),
    moneda: str = Form("EUR"),
    concepto: str | None = Form(None),
    nif_proveedor: str | None = Form(None),
    iva: str | None = Form(None),
    total_eur: str | None = Form(None),
    evidencia: UploadFile | None = File(None),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: GastosService = Depends(deps.get_gastos_service),
) -> GastoOut:
    try:
        gasto_in = GastoCreate(
            proveedor=proveedor,
            fecha=_parse_fecha(fecha),
            total_chf=total_chf,
            categoria=categoria,
            concepto=concepto,
            moneda=moneda,
            nif_proveedor=nif_proveedor,
            iva=_optional_float("iva", iva),
            total_eur=_optional_float("total_eur", total_eur),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    evidencia_bytes: bytes | None = None
    evidencia_filename: str | None = None
    evidencia_content_type: str | None = None
    if evidencia is not None:
        evidencia_bytes = await evidencia.read()
        evidencia_filename = evidencia.filename
        evidencia_content_type = evidencia.content_type

    try:
        return await service.create_gasto(
            empresa_id=current_user.empresa_id,
            empleado=current_user.username,
            gasto_in=gasto_in,
            evidencia_bytes=evidencia_bytes,
            evidencia_filename=evidencia_filename,
            evidencia_content_type=evidencia_content_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post("/ocr-hint", response_model=None)
async def ocr_hint(
    confirm: bool = Form(False),
    proveedor: str | None = Form(None),
    fecha: str | None = Form(None),
    total_chf: str | None = Form(None),
    categoria: str | None = Form(None),
    moneda: str | None = Form("EUR"),
    concepto: str | None = Form(None),
    nif_proveedor: str | None = Form(None),
    iva: str | None = Form(None),
    total_eur: str | None = Form(None),
    evidencia: UploadFile | None = File(None),
    current_user: UserOut = Depends(deps.bind_write_context),
    service: GastosService = Depends(deps.get_gastos_service),
) -> GastoOCRHint | JSONResponse:
    """
    - `confirm=false` (defecto): ejecuta OCR y devuelve `GastoOCRHint` para revisión en UI.
    - `confirm=true`: persiste el gasto (mismos campos que POST /) usando **solo** `empresa_id` del JWT.
    """
    if confirm:
        if not proveedor or not fecha or total_chf is None or not categoria:
            raise HTTPException(
                status_code=422,
                detail="Con confirm=true se requieren proveedor, fecha, total_chf y categoria",
            )
        try:
            tc = float(total_chf)
        except ValueError as e:
            raise HTTPException(status_code=422, detail="total_chf debe ser numérico") from e
        try:
            gasto_in = GastoCreate(
                proveedor=proveedor,
                fecha=_parse_fecha(fecha),
                total_chf=tc,
                categoria=categoria,
                concepto=concepto,
                moneda=moneda or "EUR",
                nif_proveedor=nif_proveedor,
                iva=_optional_float("iva", iva),
                total_eur=_optional_float("total_eur", total_eur),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        evidencia_bytes: bytes | None = None
        evidencia_filename: str | None = None
        evidencia_content_type: str | None = None
        if evidencia is not None:
            evidencia_bytes = await evidencia.read()
            evidencia_filename = evidencia.filename
            evidencia_content_type = evidencia.content_type

        try:
            created = await service.create_gasto(
                empresa_id=current_user.empresa_id,
                empleado=current_user.username,
                gasto_in=gasto_in,
                evidencia_bytes=evidencia_bytes,
                evidencia_filename=evidencia_filename,
                evidencia_content_type=evidencia_content_type,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=created.model_dump(mode="json"))

    if evidencia is None:
        raise HTTPException(status_code=422, detail="Se requiere evidencia para OCR (confirm=false)")

    content = await evidencia.read()
    hint = await service.ocr_extract_hint(content=content, filename=evidencia.filename or "evidencia")
    return hint
