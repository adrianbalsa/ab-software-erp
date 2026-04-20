"""Rutas ESG bajo ``/api/v1/admin/esg`` (administración tenant + export auditoría)."""

from __future__ import annotations

import io
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.models.enums import UserRole
from app.schemas.user import UserOut
from app.services.esg_audit_service import EsgAuditService
from app.services.esg_export_service import EsgExportService

router = APIRouter(prefix="/esg", tags=["ESG — administración"])


def _admin_may_access_empresa(*, admin: UserOut, target_empresa_id: str) -> bool:
    tid = str(target_empresa_id or "").strip()
    if not tid:
        return False
    if admin.role in (UserRole.SUPERADMIN, UserRole.DEVELOPER):
        return True
    return str(admin.empresa_id) == tid


async def _certificate_row_empresa_id(db: SupabaseAsync, *, verification_code: str) -> str | None:
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


@router.get(
    "/audit-export/{empresa_id}",
    summary="Export ISO 14083 (JSON/CSV) sin PII para auditoría",
)
async def get_esg_audit_export(
    empresa_id: str = Path(..., description="UUID empresa"),
    fecha_inicio: date = Query(..., description="Inicio inclusive"),
    fecha_fin: date = Query(..., description="Fin inclusive"),
    formato: Literal["csv", "json"] = Query("csv", description="csv (coma+BOM) o json"),
    admin_user: UserOut = Depends(deps.require_admin_user),
    export_svc: EsgExportService = Depends(deps.get_esg_export_service_admin),
) -> StreamingResponse:
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual que fecha_inicio.",
        )
    eid = str(empresa_id).strip()
    if not _admin_may_access_empresa(admin=admin_user, target_empresa_id=eid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado a exportar datos de esta empresa.",
        )

    if formato == "json":
        body = await export_svc.export_json_bytes(
            empresa_id=eid,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
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

    fn = f"esg_audit_export_{eid[:8]}_{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}.{ext}"
    return StreamingResponse(
        io.BytesIO(body),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.post(
    "/certificate/externally-verify/{verification_code}",
    summary="Marca certificado ESG como externally_verified (admin empresa)",
)
async def post_esg_certificate_externally_verify_admin(
    verification_code: str,
    admin_user: UserOut = Depends(deps.require_admin_user),
    db: SupabaseAsync = Depends(deps.get_db_admin),
    audit: EsgAuditService = Depends(deps.get_esg_audit_service_admin),
) -> dict[str, Any]:
    cert_eid = await _certificate_row_empresa_id(db, verification_code=verification_code)
    if cert_eid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificado no encontrado")
    if not _admin_may_access_empresa(admin=admin_user, target_empresa_id=cert_eid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado a verificar este certificado.",
        )
    try:
        return await audit.mark_certificate_externally_verified(verification_code=verification_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
