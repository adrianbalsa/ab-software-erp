from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api import deps
from app.core.config import get_settings
from app.core.alerts import schedule_critical_error_alert
from app.core.verifactu import verify_invoice_chain
from app.core.verifactu_chain_repair import diagnose_fingerprint_hash_chain, repair_recommendations
from app.core.verifactu_qr import generate_verifactu_qr_with_url
from app.services.aeat_qr_service import qr_png_bytes_from_url
from app.core.crypto import pii_crypto
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.facturas_service import FacturasService
from app.services.verifactu_fingerprint_audit import (
    load_cliente_nif_map_for_facturas,
    materialize_factura_rows_for_fingerprint_verify,
)
from app.services.verifactu_service import VerifactuService

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HTTPError(BaseModel):
    detail: str


class RetryPendingVerifactuOut(BaseModel):
    processed: int
    success: int
    failed: int

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
    Valida las últimas 50 facturas del tenant: recalcula huella de emisión y comprueba ``hash_anterior`` / almacenado.
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
    lang: str | None = Query(
        default=None,
        description="Informe legible: es | en (por defecto preferencia de usuario/empresa).",
    ),
    _: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
    current_user: UserOut = Depends(deps.get_current_user),
) -> dict[str, object]:
    eid = str(current_user.empresa_id)
    q = filter_not_deleted(
        db.table("facturas")
        .select(
            "id,cliente,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,"
            "fingerprint_hash,previous_fingerprint"
        )
        .eq("empresa_id", eid)
        .order("fecha_emision", desc=False)
        .order("numero_secuencial", desc=False)
        .order("id", desc=False)
    )
    if ejercicio is not None:
        q = q.gte("fecha_emision", f"{ejercicio:04d}-01-01").lt("fecha_emision", f"{ejercicio + 1:04d}-01-01")

    res = await db.execute(q)
    rows: list[dict] = (res.data or []) if hasattr(res, "data") else []
    nif_map = await load_cliente_nif_map_for_facturas(db, empresa_id=eid, rows=rows)
    rows_m = materialize_factura_rows_for_fingerprint_verify(rows, cliente_nif_map=nif_map)
    eff_lang = lang or getattr(current_user, "preferred_language", None) or "es"
    report = verify_invoice_chain(rows_m, lang=eff_lang)
    return {
        "ejercicio": ejercicio,
        "lang": eff_lang,
        **report,
    }


@router.get(
    "/audit/chain-repair",
    summary="Diagnóstico de cadena fiscal y recomendaciones (sin modificar datos)",
)
async def audit_chain_repair(
    lang: str | None = Query(
        default=None,
        description="Recomendaciones legibles: es | en (por defecto preferencia de usuario/empresa).",
    ),
    _: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
    current_user: UserOut = Depends(deps.get_current_user),
) -> dict[str, object]:
    """
    Cruza ``verificar_cadena_facturas`` (hash_registro / huella) con el análisis de
    ``fingerprint_hash`` / ``previous_fingerprint``. Solo lectura; la reparación efectiva
    requiere intervención manual o script bajo copia de seguridad.
    """
    eid = str(current_user.empresa_id)
    svc = VerifactuService(db)
    db_audit = await svc.verificar_cadena_facturas(empresa_id=eid, limit=500)
    q = filter_not_deleted(
        db.table("facturas")
        .select(
            "id,cliente,numero_secuencial,num_factura,numero_factura,fecha_emision,"
            "nif_emisor,total_factura,fingerprint_hash,previous_fingerprint"
        )
        .eq("empresa_id", eid)
        .eq("bloqueado", True)
        .order("numero_secuencial", desc=False)
        .order("id", desc=False)
    )
    res = await db.execute(q)
    rows: list[dict] = list((res.data or []) if hasattr(res, "data") else [])
    nif_map = await load_cliente_nif_map_for_facturas(db, empresa_id=eid, rows=rows)
    rows_m = materialize_factura_rows_for_fingerprint_verify(rows, cliente_nif_map=nif_map)
    fh = diagnose_fingerprint_hash_chain(rows_m)
    eff_lang = lang or getattr(current_user, "preferred_language", None) or "es"
    recs = repair_recommendations(
        db_discrepancies=db_audit.get("discrepancies"),
        fingerprint_hash_report=fh,
        lang=eff_lang,
    )
    return {
        "empresa_id": eid,
        "lang": eff_lang,
        "hash_factura_verification": db_audit,
        "fingerprint_hash_chain": fh,
        "recommendations": recs,
    }


@router.post(
    "/retry-pending",
    response_model=RetryPendingVerifactuOut,
    summary="Reintentar envíos VeriFactu pendientes (AEAT)",
)
async def retry_pending_verifactu(
    current_user: UserOut = Depends(deps.require_role("owner")),
    db: SupabaseAsync = Depends(deps.get_db),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> RetryPendingVerifactuOut:
    """
    Reintenta el envío a la AEAT para facturas con ``aeat_sif_estado = pendiente_envio``.

    - Solo facturas **creadas** en las últimas **48 h** (margen de seguridad).
    - Máximo **50** facturas por llamada.
    - Ejecución **secuencial** con registro en log por factura.
    """
    eid = str(current_user.empresa_id)
    cfg = get_settings()
    if not cfg.AEAT_VERIFACTU_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Envío AEAT desactivado (AEAT_VERIFACTU_ENABLED).",
        )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    cutoff_iso = cutoff.isoformat()

    q = filter_not_deleted(
        db.table("facturas")
        .select("id, created_at")
        .eq("empresa_id", eid)
        .eq("aeat_sif_estado", "pendiente_envio")
        .gte("created_at", cutoff_iso)
        .order("created_at", desc=False)
        .limit(50)
    )
    res = await db.execute(q)
    rows: list[dict] = list((res.data or []) if hasattr(res, "data") else [])
    ids: list[int] = []
    for r in rows:
        try:
            ids.append(int(r["id"]))
        except (TypeError, ValueError, KeyError):
            continue

    processed = 0
    success = 0
    failed = 0
    uid = str(current_user.usuario_id) if current_user.usuario_id else None

    for fid in ids:
        processed += 1
        try:
            out = await facturas.reenviar_aeat_sif(
                empresa_id=eid,
                factura_id=fid,
                usuario_id=uid,
            )
            est = str(out.get("aeat_sif_estado") or "").strip().lower()
            queued = str(out.get("status") or "").strip().lower() == "queued"
            if queued and est == "pendiente_envio":
                success += 1
                logger.info(
                    "retry-pending: factura_id=%s encolada para AEAT (job_id=%s)",
                    fid,
                    out.get("job_id"),
                )
            else:
                failed += 1
                logger.warning(
                    "retry-pending: factura_id=%s no se pudo encolar correctamente (estado=%s)",
                    fid,
                    est,
                )
        except ValueError as exc:
            failed += 1
            logger.warning(
                "retry-pending: factura_id=%s argumentos o estado inválido: %s",
                fid,
                exc,
            )
        except Exception:
            failed += 1
            logger.exception(
                "retry-pending: factura_id=%s error no clasificado al reenviar AEAT",
                fid,
            )

    return RetryPendingVerifactuOut(processed=processed, success=success, failed=failed)


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
        .select(
            "id,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,"
            "fingerprint_hash,hash_registro,hash_factura,qr_code_url,qr_content"
        )
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
    stored_url = str(row.get("qr_code_url") or row.get("qr_content") or "").strip()
    if stored_url:
        try:
            qr_bytes = qr_png_bytes_from_url(stored_url)
            aeat_url = stored_url
        except Exception:
            stored_url = ""
    if not stored_url:
        invoice_payload = {
            "nif_emisor": nif_plain,
            "num_factura": row.get("num_factura") or row.get("numero_factura"),
            "fecha_expedicion": row.get("fecha_emision"),
            "importe_total": row.get("total_factura"),
            "hash_registro": row.get("hash_registro"),
            "hash_factura": row.get("hash_factura"),
            "fingerprint_hash": row.get("fingerprint_hash"),
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
