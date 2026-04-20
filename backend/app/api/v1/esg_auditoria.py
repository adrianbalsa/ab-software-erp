from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api import deps
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.esg import (
    EsgAnnualMemoryExecutiveOut,
    EsgAnnualMemoryNormativaOut,
    EsgAnnualMemoryOut,
    EsgAnnualMemoryTopClienteOut,
    EsgAuditReadyOut,
)
from app.schemas.user import UserOut
from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE
from app.core.esg_engine import calculate_co2_emissions, calculate_nox_emissions
from app.services.esg_audit_service import EsgAuditService
from app.services.esg_export_service import EsgExportService

router = APIRouter(prefix="/esg")


async def _empresa_id_for_verification_code_admin(
    db: SupabaseAsync, *, verification_code: str
) -> str | None:
    code = str(verification_code or "").strip()
    if len(code) < 8:
        return None
    try:
        res: Any = await db.execute(
            db.table("esg_certificate_documents")
            .select("empresa_id")
            .eq("verification_code", code)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        return None
    if not rows:
        return None
    raw = rows[0].get("empresa_id")
    return str(raw).strip() if raw else None


class EsgCertificateRegistryItem(BaseModel):
    """Certificado emitido (código QR público; sin subject_id)."""

    verification_code: str
    verification_status: str
    subject_type: str
    certificate_id: str
    created_at: datetime | None = None


class EsgAuditFuelMonthlyOut(BaseModel):
    mes: str = Field(..., description="YYYY-MM")
    litros_consumidos: float = Field(..., ge=0)
    co2_emitido_kg: float = Field(..., ge=0)
    co2_baseline_kg: float = Field(..., ge=0)
    co2_ahorro_kg: float = Field(..., ge=0)


class EsgAuditFuelAnnualOut(BaseModel):
    year: int
    empresa_id: str
    total_litros_consumidos: float = Field(..., ge=0)
    total_co2_emitido_kg: float = Field(..., ge=0)
    total_co2_baseline_kg: float = Field(..., ge=0)
    total_co2_ahorro_kg: float = Field(..., ge=0)
    meses: list[EsgAuditFuelMonthlyOut]


_CO2_KG_PER_LITRO_DIESEL_A = ISO_14083_DIESEL_CO2_KG_PER_LITRE


@router.get(
    "/reporte-anual",
    response_model=EsgAuditFuelAnnualOut,
    status_code=status.HTTP_200_OK,
    summary="Reporte anual de combustible y CO₂ (auditoría)",
)
async def esg_reporte_anual_fuel(
    year: int = Query(date.today().year, ge=2000, le=2100),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> EsgAuditFuelAnnualOut:
    """
    Emisiones agregadas por mes para el Dashboard Económico (Scope fuel).

    - `co2_emitido_kg`: calculado con bonus Euro VI (si aplica) en importación de combustible.
    - `co2_baseline_kg`: litros × 2.67 kg CO2/L (sin bonus).
    - `co2_ahorro_kg`: baseline − emitido.
    """

    eid = str(current_user.empresa_id)
    if not eid.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empresa_id inválido"
        )

    fi = date(year, 1, 1).isoformat()
    ff = date(year, 12, 31).isoformat()

    q = filter_not_deleted(
        db.table("esg_auditoria")
        .select("fecha,litros_consumidos,co2_emitido_kg")
        .eq("empresa_id", eid)
        .gte("fecha", fi)
        .lte("fecha", ff)
    )

    res: Any = await db.execute(q)
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []

    # Acumuladores por mes (1..12)
    acc = {
        m: {
            "litros": 0.0,
            "co2_emitido": 0.0,
        }
        for m in range(1, 13)
    }

    for r in rows:
        raw_fecha = r.get("fecha")
        if raw_fecha is None:
            continue
        try:
            d = date.fromisoformat(str(raw_fecha))
        except ValueError:
            continue

        m = d.month
        litros = float(r.get("litros_consumidos") or 0.0)
        co2_emitido = float(r.get("co2_emitido_kg") or 0.0)
        acc[m]["litros"] += max(0.0, litros)
        acc[m]["co2_emitido"] += max(0.0, co2_emitido)

    meses_out: list[EsgAuditFuelMonthlyOut] = []
    total_litros = 0.0
    total_emitido = 0.0
    total_baseline = 0.0

    for m in range(1, 13):
        litros_m = acc[m]["litros"]
        co2_emitido_m = acc[m]["co2_emitido"]
        co2_baseline_m = litros_m * _CO2_KG_PER_LITRO_DIESEL_A
        co2_ahorro_m = max(0.0, co2_baseline_m - co2_emitido_m)

        total_litros += litros_m
        total_emitido += co2_emitido_m
        total_baseline += co2_baseline_m

        meses_out.append(
            EsgAuditFuelMonthlyOut(
                mes=f"{year}-{m:02d}",
                litros_consumidos=round(litros_m, 4),
                co2_emitido_kg=round(co2_emitido_m, 4),
                co2_baseline_kg=round(co2_baseline_m, 4),
                co2_ahorro_kg=round(co2_ahorro_m, 4),
            )
        )

    total_ahorro = max(0.0, total_baseline - total_emitido)

    return EsgAuditFuelAnnualOut(
        year=year,
        empresa_id=eid,
        total_litros_consumidos=round(total_litros, 4),
        total_co2_emitido_kg=round(total_emitido, 4),
        total_co2_baseline_kg=round(total_baseline, 4),
        total_co2_ahorro_kg=round(total_ahorro, 4),
        meses=meses_out,
    )


@router.get(
    "/audit-ready",
    response_model=EsgAuditReadyOut,
    summary="Reporte ESG audit-ready por cliente y periodo",
)
async def esg_audit_ready_report(
    fecha_inicio: date = Query(..., description="Inicio del periodo (inclusive)"),
    fecha_fin: date = Query(..., description="Fin del periodo (inclusive)"),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service=Depends(deps.get_esg_service),
) -> EsgAuditReadyOut:
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual que fecha_inicio.",
        )
    return await service.audit_ready_summary(
        empresa_id=str(current_user.empresa_id),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get(
    "/audit-ready/export",
    summary="Exportación ESG audit-ready (CSV)",
)
async def esg_audit_ready_export(
    fecha_inicio: date = Query(..., description="Inicio del periodo (inclusive)"),
    fecha_fin: date = Query(..., description="Fin del periodo (inclusive)"),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service=Depends(deps.get_esg_service),
):
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual que fecha_inicio.",
        )
    csv_bytes = await service.audit_ready_summary_csv(
        empresa_id=str(current_user.empresa_id),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    filename = f"esg_audit_ready_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/suggest-vehicle",
    summary="Sugerencia ESG de vehículo para un porte (min CO2)",
)
async def esg_suggest_vehicle(
    km_estimados: float = Query(..., ge=0, description="KM estimados del porte"),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    service=Depends(deps.get_esg_service),
) -> dict[str, str | float | None]:
    return await service.suggest_vehicle_for_porte(
        empresa_id=str(current_user.empresa_id),
        km_estimados=km_estimados,
    )


@router.get(
    "/annual-memory",
    response_model=EsgAnnualMemoryOut,
    summary="Memoria Anual de Sostenibilidad (JSON)",
)
async def esg_annual_memory(
    year: int = Query(date.today().year, ge=2000, le=2100),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> EsgAnnualMemoryOut:
    empresa_id = str(current_user.empresa_id)
    fi = date(year, 1, 1).isoformat()
    ff = date(year, 12, 31).isoformat()

    # Portes facturados del año
    q = filter_not_deleted(
        db.table("portes")
        .select("id,cliente_id,vehiculo_id,km_estimados,co2_emitido,fecha")
        .eq("empresa_id", empresa_id)
        .eq("estado", "facturado")
        .gte("fecha", fi)
        .lte("fecha", ff)
    )
    res: Any = await db.execute(q)
    porte_rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []

    # Flota para normativa EURO
    veh_ids = {str(r.get("vehiculo_id")) for r in porte_rows if r.get("vehiculo_id")}
    flota_by_id: dict[str, dict[str, Any]] = {}
    if veh_ids:
        try:
            rf: Any = await db.execute(
                filter_not_deleted(
                    db.table("flota")
                    .select("id,normativa_euro")
                    .eq("empresa_id", empresa_id)
                    .in_("id", list(veh_ids))
                )
            )
            flota_by_id = {
                str(r.get("id")): r
                for r in (rf.data or [])
                if isinstance(r, dict) and r.get("id") is not None
            }
        except Exception:
            flota_by_id = {}

    # Nombres clientes
    cliente_ids = {str(r.get("cliente_id")) for r in porte_rows if r.get("cliente_id")}
    nombres: dict[str, str] = {}
    if cliente_ids:
        try:
            rc: Any = await db.execute(
                filter_not_deleted(
                    db.table("clientes")
                    .select("id,nombre_comercial,nombre")
                    .eq("empresa_id", empresa_id)
                    .in_("id", list(cliente_ids))
                )
            )
            for r in (rc.data or []) if hasattr(rc, "data") else []:
                cid = str(r.get("id") or "").strip()
                if not cid:
                    continue
                nc = str(r.get("nombre_comercial") or "").strip()
                nm = str(r.get("nombre") or "").strip()
                nombres[cid] = nc or nm or cid
        except Exception:
            pass

    total_km = 0.0
    total_co2 = 0.0
    total_nox = 0.0
    km_euro_iii = 0.0
    km_euro_vi = 0.0
    co2_by_cliente: dict[str, float] = {}

    for r in porte_rows:
        km = float(r.get("km_estimados") or 0.0)
        total_km += max(0.0, km)
        vid = str(r.get("vehiculo_id") or "").strip()
        norma = str(flota_by_id.get(vid, {}).get("normativa_euro") or "Euro VI")

        if norma == "Euro III":
            km_euro_iii += max(0.0, km)
        if norma == "Euro VI":
            km_euro_vi += max(0.0, km)

        co2_raw = r.get("co2_emitido")
        if co2_raw is not None:
            try:
                co2 = max(0.0, float(co2_raw))
            except (TypeError, ValueError):
                co2 = 0.0
        else:
            co2 = calculate_co2_emissions(km, norma)
        nox = calculate_nox_emissions(km, norma)

        total_co2 += co2
        total_nox += nox

        cid = str(r.get("cliente_id") or "").strip()
        if cid:
            co2_by_cliente[cid] = co2_by_cliente.get(cid, 0.0) + co2

    eficiencia = (total_co2 / total_km) if total_km > 0 else 0.0

    pct_iii = (km_euro_iii / total_km) * 100.0 if total_km > 0 else 0.0
    pct_vi = (km_euro_vi / total_km) * 100.0 if total_km > 0 else 0.0

    top = sorted(co2_by_cliente.items(), key=lambda x: x[1], reverse=True)[:5]
    top_clientes = [
        EsgAnnualMemoryTopClienteOut(
            cliente_id=cid,
            cliente_nombre=nombres.get(cid),
            co2_kg=round(val, 4),
        )
        for cid, val in top
    ]

    metodologia = (
        "Factores de emisión basados en normativa EURO (III–VI). "
        "CO2: kg/km por normativa. NOx: g/km por normativa convertido a kg. "
        "KM estimados de portes facturados."
    )

    return EsgAnnualMemoryOut(
        year=year,
        empresa_id=empresa_id,
        resumen_ejecutivo=EsgAnnualMemoryExecutiveOut(
            total_co2_kg=round(total_co2, 4),
            total_nox_kg=round(total_nox, 4),
            total_km=round(total_km, 4),
            eficiencia_media_kg_co2_km=round(eficiencia, 4),
        ),
        desglose_normativa=EsgAnnualMemoryNormativaOut(
            pct_euro_iii=round(pct_iii, 4),
            pct_euro_vi=round(pct_vi, 4),
        ),
        top_clientes=top_clientes,
        metodologia=metodologia,
    )


@router.get(
    "/certificate-registry",
    response_model=list[EsgCertificateRegistryItem],
    summary="Registro de certificados ESG (códigos QR / estado, sin subject_id)",
)
async def list_esg_certificate_registry(
    limit: int = Query(50, ge=1, le=200),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager", "gestor")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> list[EsgCertificateRegistryItem]:
    eid = str(current_user.empresa_id)
    try:
        q = (
            db.table("esg_certificate_documents")
            .select("verification_code,verification_status,subject_type,certificate_id,created_at")
            .eq("empresa_id", eid)
            .order("created_at", desc=True)
            .limit(limit)
        )
        res: Any = await db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        rows = []
    out: list[EsgCertificateRegistryItem] = []
    for r in rows:
        vc = r.get("verification_code")
        if vc is None:
            continue
        out.append(
            EsgCertificateRegistryItem(
                verification_code=str(vc),
                verification_status=str(r.get("verification_status") or ""),
                subject_type=str(r.get("subject_type") or ""),
                certificate_id=str(r.get("certificate_id") or ""),
                created_at=_parse_registry_created_at(r.get("created_at")),
            )
        )
    return out


def _parse_registry_created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@router.get(
    "/emissions-export-iso14083",
    summary="Export ISO 14083 agregado sin PII (CSV o JSON)",
)
async def esg_emissions_export_iso14083(
    fecha_inicio: date = Query(..., description="Inicio inclusive"),
    fecha_fin: date = Query(..., description="Fin inclusive"),
    formato: Literal["csv", "json"] = Query("csv"),
    for_external_auditor: bool = Query(
        False,
        description="Si true y formato=json, omite empresa_id en meta (entrega a terceros).",
    ),
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager", "gestor")),
    export_svc: EsgExportService = Depends(deps.get_esg_export_service),
) -> StreamingResponse:
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual que fecha_inicio.",
        )
    eid = str(current_user.empresa_id)
    if formato == "json":
        body = await export_svc.export_json_bytes(
            empresa_id=eid,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            redact_workspace=for_external_auditor,
        )
        media = "application/json"
        ext = "json"
    else:
        body = await export_svc.export_csv_bytes(
            empresa_id=eid,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        media = "text/csv; charset=utf-8"
        ext = "csv"
    fn = f"esg_iso14083_export_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.{ext}"
    return StreamingResponse(
        io.BytesIO(body),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.post(
    "/certificate/externally-verify/{verification_code}",
    summary="Marca certificado como externally_verified (solo owner del tenant)",
)
async def post_esg_certificate_externally_verify_owner(
    verification_code: str = Path(..., min_length=8),
    current_user: UserOut = Depends(deps.require_role("owner")),
    db_admin: SupabaseAsync = Depends(deps.get_db_admin),
    audit: EsgAuditService = Depends(deps.get_esg_audit_service_admin),
) -> dict[str, Any]:
    """
    Tras validación manual o webhook de certificadora, el propietario puede cerrar el estado.
    Requiere que el certificado esté en ``pending_external_audit`` y pertenezca al tenant.
    """
    cert_eid = await _empresa_id_for_verification_code_admin(db_admin, verification_code=verification_code)
    if cert_eid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificado no encontrado")
    if str(current_user.empresa_id) != cert_eid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado a verificar este certificado.",
        )
    try:
        return await audit.mark_certificate_externally_verified(verification_code=verification_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

