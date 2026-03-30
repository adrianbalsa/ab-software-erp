from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, Query, Request

from app.api import deps
from app.core.alerts import schedule_critical_error_alert
from app.core.verifactu import verify_invoice_chain
from app.core.verifactu_qr import generate_verifactu_qr_with_url
from app.core.crypto import pii_crypto
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.verifactu_service import VerifactuService

from pydantic import BaseModel

class HTTPError(BaseModel):
    detail: str

router = APIRouter()

@router.get(
    "/verificar-cadena",
    summary="Verificar cadena de hash VeriFactu",
    responses={404: {"description": "No encontrado", "model": HTTPError}, 400: {"description": "Petición inválida", "model": HTTPError}}
)
async def verificar_cadena(
    request: Request,
    current_user: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    db: SupabaseAsync = Depends(deps.get_db),
) -> dict:
    """
    Valida las últimas 50 facturas del tenant: recalcula ``hash_factura`` y comprueba el encadenamiento.
    Si hay discrepancias, dispara alerta crítica (webhook configurado).
    """
    svc = VerifactuService(db)
    eid = str(current_user.empresa_id)
    result = await svc.verificar_cadena_facturas(empresa_id=eid, limit=50)
    discrepancies = result.get("discrepancies") or []
    if discrepancies:
        schedule_critical_error_alert(
            request=request,
            error_detail=(
                f"VeriFactu: cadena de hash rota (empresa_id={eid}, "
                f"discrepancias={len(discrepancies)})"
            ),
        )
    return result


@router.get(
    "/audit/verify-chain",
    summary="Auditoría de integridad de cadena fiscal",
    responses={404: {"description": "No encontrado", "model": HTTPError}, 400: {"description": "Parámetros inválidos", "model": HTTPError}}
)
async def audit_verify_chain(
    ejercicio: int | None = Query(default=None, ge=2000, le=2100),
    _: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
    current_user: UserOut = Depends(deps.get_current_user),
) -> dict[str, object]:
    eid = str(current_user.empresa_id)
    q = filter_not_deleted(
        db.table("facturas")
        .select("id,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,fingerprint_hash,previous_fingerprint")
        .eq("empresa_id", eid)
        .order("fecha_emision", desc=False)
        .order("numero_secuencial", desc=False)
        .order("id", desc=False)
    )
    if ejercicio is not None:
        q = q.gte("fecha_emision", f"{ejercicio:04d}-01-01").lt("fecha_emision", f"{ejercicio + 1:04d}-01-01")

    res = await db.execute(q)
    rows: list[dict] = (res.data or []) if hasattr(res, "data") else []
    report = verify_invoice_chain(rows)
    return {
        "ejercicio": ejercicio,
        **report,
    }


@router.get(
    "/audit/qr-preview/{factura_id}",
    summary="Previsualización QR VeriFactu de factura",
    responses={
        404: {"description": "Factura no encontrada o sin acceso", "model": HTTPError},
        400: {"description": "Petición inválida", "model": HTTPError}
    }
)
async def audit_qr_preview(
    factura_id: int,
    _: UserOut = Depends(deps.require_role("owner")),
    _tenant_guard: None = Depends(
        deps.require_tenant_resource(table_name="facturas", path_param="factura_id")
    ),
    db: SupabaseAsync = Depends(deps.get_db),
    current_user: UserOut = Depends(deps.get_current_user),
) -> dict[str, object]:
    eid = str(current_user.empresa_id)
    res = await db.execute(
        db.table("facturas")
        .select("id,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,fingerprint_hash")
        .eq("empresa_id", eid)
        .eq("id", int(factura_id))
        .limit(1)
    )
    rows: list[dict] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        return {"found": False}

    row = dict(rows[0])
    raw_nif = str(row.get("nif_emisor") or "").strip()
    nif_plain = pii_crypto.decrypt_pii(raw_nif) or raw_nif
    invoice_payload = {
        "nif_emisor": nif_plain,
        "num_factura": row.get("num_factura") or row.get("numero_factura"),
        "fecha_expedicion": row.get("fecha_emision"),
        "importe_total": row.get("total_factura"),
    }
    qr_bytes, aeat_url = generate_verifactu_qr_with_url(invoice_payload)
    return {
        "found": True,
        "factura_id": row.get("id"),
        "numero_factura": row.get("numero_factura") or row.get("num_factura"),
        "fecha_emision": row.get("fecha_emision"),
        "total_factura": row.get("total_factura"),
        "fingerprint_hash": row.get("fingerprint_hash"),
        "aeat_url": aeat_url,
        "qr_png_base64": base64.b64encode(qr_bytes).decode("ascii"),
    }
