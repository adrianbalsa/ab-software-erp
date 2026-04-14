"""
Cliente VeriFactu AEAT: XML de registro (alineado con ``verifactu_sender``) y envío HTTP(S)
con mTLS al endpoint de pruebas o producción configurado.

``send_to_aeat`` delega en ``enviar_registro_y_persistir`` y, si la AEAT acepta el registro,
persiste ``aeat_sif_estado = 'enviado_ok'`` en ``public.facturas``.
"""

from __future__ import annotations

from typing import Any

from app.services.suministro_lr_xml import FacturaRectificadaRefAEAT
from app.services.suministro_lr_xml import RegistroAnteriorAEAT
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.crypto import pii_crypto
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.verifactu_sender import (
    generar_xml_registro_facturacion_alta,
    enviar_registro_y_persistir,
)


def build_verifactu_xml_registro_alta(
    *,
    factura: dict[str, Any],
    empresa: dict[str, Any],
    cliente: dict[str, Any],
    hash_registro: str,
    fingerprint: str,
    prev_fingerprint: str | None,
    registro_anterior: RegistroAnteriorAEAT | None = None,
    rectificada: FacturaRectificadaRefAEAT | None = None,
) -> str:
    """XML interno de alta (misma firma que el envío oficial vía ``verifactu_sender``)."""
    return generar_xml_registro_facturacion_alta(
        factura=factura,
        empresa=empresa,
        cliente=cliente,
        hash_registro=hash_registro,
        fingerprint=fingerprint,
        prev_fingerprint=prev_fingerprint,
        registro_anterior=registro_anterior,
        rectificada=rectificada,
    )


async def send_to_aeat(
    db: SupabaseAsync,
    *,
    invoice_id: int,
    empresa_id: str | UUID,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    POST asíncrono al servicio AEAT (URL de pruebas si ``AEAT_VERIFACTU_USE_PRODUCTION`` es falso
    y hay ``AEAT_VERIFACTU_SUBMIT_URL_TEST``), actualiza ``verifactu_envios`` y ``aeat_sif_*``.
    Si la respuesta se interpreta como aceptada, ``aeat_sif_estado`` pasa a ``enviado_ok``.
    """
    eid = str(empresa_id).strip()
    fid = int(invoice_id)
    cfg = settings or get_settings()

    if not cfg.AEAT_VERIFACTU_ENABLED:
        raise ValueError("Envío AEAT desactivado (AEAT_VERIFACTU_ENABLED).")

    res: Any = await db.execute(
        db.table("facturas").select("*").eq("id", fid).eq("empresa_id", eid).limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        raise ValueError("Factura no encontrada")
    fr = dict(rows[0])
    if not fr.get("is_finalized"):
        raise ValueError("Solo se puede enviar a la AEAT una factura finalizada.")
    if not str(fr.get("fingerprint") or "").strip():
        raise ValueError("La factura no tiene huella fingerprint de registro.")

    raw_nif_fr = fr.get("nif_emisor")
    if isinstance(raw_nif_fr, str) and raw_nif_fr.strip():
        fr["nif_emisor"] = pii_crypto.decrypt_pii(raw_nif_fr) or raw_nif_fr

    re: Any = await db.execute(db.table("empresas").select("*").eq("id", eid).limit(1))
    erows: list[dict[str, Any]] = (re.data or []) if hasattr(re, "data") else []
    if not erows:
        raise ValueError("Empresa no encontrada")
    emp = dict(erows[0])
    raw_emp_nif = emp.get("nif")
    if isinstance(raw_emp_nif, str) and raw_emp_nif.strip():
        emp["nif"] = pii_crypto.decrypt_pii(raw_emp_nif) or raw_emp_nif

    cid = str(fr.get("cliente") or "").strip()
    cli_map: dict[str, Any] = {"nif": "", "nombre": ""}
    if cid:
        try:
            rcli: Any = await db.execute(
                filter_not_deleted(
                    db.table("clientes")
                    .select("*")
                    .eq("empresa_id", eid)
                    .eq("id", cid)
                    .limit(1)
                )
            )
            crd: list[dict[str, Any]] = (rcli.data or []) if hasattr(rcli, "data") else []
            if crd:
                nif_c = crd[0].get("nif")
                if isinstance(nif_c, str) and nif_c.strip():
                    crd[0]["nif"] = pii_crypto.decrypt_pii(nif_c) or nif_c
                cli_map = {
                    "nif": str(crd[0].get("nif") or "").strip(),
                    "nombre": str(crd[0].get("nombre") or "").strip(),
                }
        except Exception:
            pass

    merged = await enviar_registro_y_persistir(
        db,
        settings=cfg,
        empresa_id=eid,
        empresa_row=emp,
        factura_row=fr,
        cliente=cli_map,
    )

    est = str(merged.get("aeat_sif_estado") or "").strip().lower()
    if est == "pendiente_envio":
        return merged
    if est == "aceptado":
        await db.execute(
            db.table("facturas")
            .update({"aeat_sif_estado": "enviado_ok"})
            .eq("id", fid)
            .eq("empresa_id", eid)
        )
        merged = {**merged, "aeat_sif_estado": "enviado_ok"}

    return merged
