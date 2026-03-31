from __future__ import annotations

import base64
import csv
import io
import json
import os
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import anyio
from starlette.background import BackgroundTasks

from app.core.config import get_settings
from app.core.verifactu import GENESIS_HASH, generate_invoice_hash
from app.core.fiscal_logic import compute_invoice_fingerprint
from app.core.math_engine import (
    MathEngine,
    as_float_fiat,
    decimal_to_db_numeric,
    negate_fiat_for_rectificativa,
    quantize_financial,
    require_non_negative_precio_pactado,
    round_fiat,
    safe_divide,
    to_decimal,
)
from app.core.plans import PLAN_ENTERPRISE, fetch_empresa_plan, normalize_plan
from app.db.session import get_engine
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.integrations.pdf_adapter import generar_pdf_factura_base64
from app.schemas.cliente import ClienteOut
from app.schemas.factura import (
    FacturaCreateFromPortes,
    FacturaGenerateResult,
    FacturaOut,
    FacturaPdfDataOut,
    FacturaPdfEmisorOut,
    FacturaPdfLineaOut,
    FacturaPdfReceptorOut,
    FacturaRecalculateOut,
)
from app.services.aeat_qr_service import (
    build_srei_verifactu_url,
    generar_qr_verifactu,
    qr_png_bytes_from_url,
)
from app.services.aeat_xml_service import generar_xml_alta_factura
from app.services.auditoria_service import AuditoriaService
from app.services.eco_service import co2_emitido_desde_porte_row
from app.services.report_service import _parse_porte_lineas_snapshot
from app.services.aeat_client import send_to_aeat
from app.services.verifactu_service import VerifactuService
from app.core.crypto import pii_crypto


def _clone_snapshot_con_importes_negativos(snapshot: Any) -> list[dict[str, Any]]:
    if not isinstance(snapshot, list):
        return []
    out: list[dict[str, Any]] = []
    for item in snapshot:
        if not isinstance(item, dict):
            continue
        line = dict(item)
        line["precio_pactado"] = float(negate_fiat_for_rectificativa(line.get("precio_pactado")))
        out.append(line)
    return out


def _as_empresa_id_str(empresa_id: str | UUID) -> str:
    return str(empresa_id).strip()


def _safe_zip_label(s: str) -> str:
    t = (s or "").strip()
    if not t:
        return "Empresa"
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in t)[:80]


def _fecha_emision_str(row: dict[str, Any]) -> str:
    raw = row.get("fecha_emision")
    if raw is None:
        return ""
    s = str(raw).strip()
    return s[:10] if len(s) >= 10 else s


def _numero_factura_str(row: dict[str, Any]) -> str:
    return str(row.get("numero_factura") or row.get("num_factura") or "").strip()


def _hash_verifactu(row: dict[str, Any]) -> str:
    return str(row.get("hash_registro") or row.get("hash_factura") or "").strip()


def _factura_pk(value: Any) -> int:
    if value is None:
        raise ValueError("Factura sin id")
    if isinstance(value, bool):
        raise ValueError("Factura sin id")
    if isinstance(value, int):
        return value
    return int(value)


def _fecha_para_finalizar_iso(row: dict[str, Any]) -> str:
    raw = row.get("fecha_emision")
    if raw is None:
        return ""
    if hasattr(raw, "isoformat"):
        try:
            return raw.isoformat()[:10]
        except Exception:
            pass
    s = str(raw).strip()
    return s[:10] if len(s) >= 10 else s


def _pg_finalizar_factura_verifactu(*, empresa_id: str, factura_id: int) -> dict[str, Any]:
    """
    Transacción única en Postgres: bloqueo consultivo por empresa, ``FOR UPDATE`` de la factura,
    lectura del último ``fingerprint`` finalizado, cálculo de huella y ``UPDATE`` autorizado
    por el trigger de inmutabilidad (paso a ``is_finalized``).
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import get_engine as _ge
    from app.services.verifactu_service import VerifactuService

    eng = _ge()
    if eng is None:
        raise RuntimeError("postgres_engine_unavailable")

    try:
        with eng.begin() as conn:
            conn.execute(
                text("SELECT pg_advisory_xact_lock(abs(hashtext(CAST(:gk AS text))))"),
                {"gk": str(empresa_id)},
            )
            row_m = conn.execute(
                text(
                    """
                    SELECT f.*, c.nif AS _cliente_nif_join
                    FROM public.facturas f
                    LEFT JOIN public.clientes c
                      ON c.id = f.cliente AND c.empresa_id = f.empresa_id
                    WHERE f.id = :fid AND f.empresa_id = CAST(:eid AS uuid)
                    FOR UPDATE OF f
                    """
                ),
                {"fid": int(factura_id), "eid": str(empresa_id)},
            ).mappings().first()
            if row_m is None:
                raise ValueError("Factura no encontrada")
            r = dict(row_m)
            if bool(r.get("is_finalized")):
                raise ValueError("La factura ya está finalizada")
            hr = str(r.get("hash_registro") or r.get("hash_factura") or "").strip()
            if not hr:
                raise ValueError("Factura sin hash_registro; no puede finalizarse")

            prev_m = conn.execute(
                text(
                    """
                    SELECT fingerprint
                    FROM public.facturas
                    WHERE empresa_id = CAST(:eid AS uuid)
                      AND is_finalized = true
                      AND fingerprint IS NOT NULL
                      AND length(trim(fingerprint::text)) > 0
                    ORDER BY numero_secuencial DESC NULLS LAST, fecha_emision DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"eid": str(empresa_id)},
            ).mappings().first()
            prev_raw: str | None = None
            if prev_m and prev_m.get("fingerprint"):
                prev_raw = str(prev_m["fingerprint"]).strip() or None

            num_rect: str | None = None
            if str(r.get("tipo_factura") or "").strip().upper() == "R1":
                orig_id = r.get("factura_rectificada_id")
                if orig_id is not None:
                    om = conn.execute(
                        text(
                            """
                            SELECT num_factura, numero_factura
                            FROM public.facturas
                            WHERE id = :oid AND empresa_id = CAST(:eid AS uuid)
                            """
                        ),
                        {"oid": int(orig_id), "eid": str(empresa_id)},
                    ).mappings().first()
                    if om:
                        num_rect = str(om.get("num_factura") or om.get("numero_factura") or "").strip() or None

            nif_cli_raw = str(r.get("_cliente_nif_join") or "").strip()
            nif_cli = pii_crypto.decrypt_pii(nif_cli_raw) or nif_cli_raw
            num_f = str(r.get("num_factura") or r.get("numero_factura") or "").strip()
            fe = _fecha_para_finalizar_iso(r)
            tipo_t = str(r.get("tipo_factura") or "").strip() or None
            nif_emisor_raw = str(r.get("nif_emisor") or "").strip()
            nif_emisor_plain = pii_crypto.decrypt_pii(nif_emisor_raw) or nif_emisor_raw

            fp, prev_fp = VerifactuService.fingerprint_desde_eslabon_finalizado(
                prev_fingerprint_final=prev_raw,
                nif_emisor=nif_emisor_plain,
                nif_cliente=nif_cli,
                num_factura=num_f,
                fecha_emision=fe,
                total_factura=float(r.get("total_factura") or 0.0),
                tipo_factura=tipo_t,
                num_factura_rectificada=num_rect,
            )
            url = build_srei_verifactu_url(
                nif_emisor_plain,
                num_f,
                fe,
                float(r.get("total_factura") or 0.0),
                huella_hash=hr,
            )
            out_m = conn.execute(
                text(
                    """
                    UPDATE public.facturas
                    SET fingerprint = CAST(:fp AS text),
                        prev_fingerprint = CAST(:pfp AS text),
                        qr_content = CAST(:url AS text),
                        qr_code_url = CAST(:url AS text),
                        is_finalized = true
                    WHERE id = :fid AND empresa_id = CAST(:eid AS uuid)
                    RETURNING *
                    """
                ),
                {
                    "fp": fp,
                    "pfp": prev_fp,
                    "url": url,
                    "fid": int(factura_id),
                    "eid": str(empresa_id),
                },
            ).mappings().first()
            if out_m is None:
                raise ValueError("No se pudo actualizar la factura (fila no encontrada tras candado)")
            return dict(out_m)
    except IntegrityError as exc:
        raise ValueError(
            "No se pudo finalizar: conflicto de huella fingerprint (cadena o índice único)"
        ) from exc


class FacturasService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db
        self._audit = AuditoriaService(db)
        self._verifactu = VerifactuService(db)

    async def _get_last_fingerprint_hash(self, *, empresa_id: str) -> str:
        eid = str(empresa_id or "").strip()
        if not eid:
            return GENESIS_HASH
        try:
            res: Any = await self._db.execute(
                self._db.table("facturas")
                .select("fingerprint_hash")
                .eq("empresa_id", eid)
                .order("numero_secuencial", desc=True)
                .order("fecha_emision", desc=True)
                .order("id", desc=True)
                .limit(1)
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return GENESIS_HASH
            prev = str(rows[0].get("fingerprint_hash") or "").strip()
            return prev or GENESIS_HASH
        except Exception:
            return GENESIS_HASH

    async def list_facturas(
        self,
        *,
        empresa_id: str | UUID,
        estado_aeat: str | None = None,
    ) -> list[FacturaOut]:
        eid = _as_empresa_id_str(empresa_id)
        q = (
            self._db.table("facturas")
            .select("*")
            .eq("empresa_id", eid)
            .order("fecha_emision", desc=True)
        )
        if estado_aeat is not None and str(estado_aeat).strip():
            q = q.eq("aeat_sif_estado", str(estado_aeat).strip())
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[FacturaOut] = []
        for row in rows:
            try:
                rn = dict(row)
                raw_nif_emisor = rn.get("nif_emisor")
                if isinstance(raw_nif_emisor, str) and raw_nif_emisor.strip():
                    rn["nif_emisor"] = pii_crypto.decrypt_pii(raw_nif_emisor) or raw_nif_emisor
                out.append(FacturaOut(**rn))
            except Exception:
                continue
        return out

    async def _finalizar_factura_supabase_only(self, *, eid: str, factura_id: int) -> dict[str, Any]:
        """Finalización sin ``DATABASE_URL``: sin candado consultivo (riesgo de carrera bajo alta concurrencia)."""
        res: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", factura_id).eq("empresa_id", eid).limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Factura no encontrada")
        r = dict(rows[0])
        if bool(r.get("is_finalized")):
            raise ValueError("La factura ya está finalizada")
        hr = str(r.get("hash_registro") or r.get("hash_factura") or "").strip()
        if not hr:
            raise ValueError("Factura sin hash_registro; no puede finalizarse")

        nif_emisor_plain = str(r.get("nif_emisor") or "").strip()
        if nif_emisor_plain:
            nif_emisor_plain = pii_crypto.decrypt_pii(nif_emisor_plain) or nif_emisor_plain

        cid = str(r.get("cliente") or "").strip()
        nif_cliente = ""
        if cid:
            try:
                rc: Any = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes").select("nif").eq("empresa_id", eid).eq("id", cid).limit(1)
                    )
                )
                cr = (rc.data or []) if hasattr(rc, "data") else []
                if cr:
                    raw_nif_cli = str(cr[0].get("nif") or "").strip()
                    nif_cliente = pii_crypto.decrypt_pii(raw_nif_cli) or raw_nif_cli
            except Exception:
                pass

        prev_raw = await self._verifactu.ultima_fingerprint_factura_finalizada(empresa_id=eid)

        num_rect: str | None = None
        if str(r.get("tipo_factura") or "").strip().upper() == "R1":
            orig_id = r.get("factura_rectificada_id")
            if orig_id is not None:
                ro: Any = await self._db.execute(
                    self._db.table("facturas")
                    .select("num_factura, numero_factura")
                    .eq("empresa_id", eid)
                    .eq("id", int(orig_id))
                    .limit(1)
                )
                orows = (ro.data or []) if hasattr(ro, "data") else []
                if orows:
                    om = orows[0]
                    num_rect = str(om.get("num_factura") or om.get("numero_factura") or "").strip() or None

        num_f = str(r.get("num_factura") or r.get("numero_factura") or "").strip()
        fe = _fecha_para_finalizar_iso(r)
        tipo_t = str(r.get("tipo_factura") or "").strip() or None

        fp, prev_fp = VerifactuService.fingerprint_desde_eslabon_finalizado(
            prev_fingerprint_final=prev_raw,
            nif_emisor=nif_emisor_plain,
            nif_cliente=nif_cliente,
            num_factura=num_f,
            fecha_emision=fe,
            total_factura=float(r.get("total_factura") or 0.0),
            tipo_factura=tipo_t,
            num_factura_rectificada=num_rect,
        )
        url = build_srei_verifactu_url(
            nif_emisor_plain,
            num_f,
            fe,
            float(r.get("total_factura") or 0.0),
            huella_hash=hr,
        )
        try:
            await self._db.execute(
                self._db.table("facturas")
                .update(
                    {
                        "fingerprint": fp,
                        "prev_fingerprint": prev_fp,
                        "qr_content": url,
                        "qr_code_url": url,
                        "is_finalized": True,
                    }
                )
                .eq("id", factura_id)
                .eq("empresa_id", eid)
            )
        except Exception as exc:
            raise ValueError(
                "No se pudo finalizar la factura (actualización Supabase). "
                "Si la huella ya existe, revise la cadena."
            ) from exc

        res2: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", factura_id).eq("empresa_id", eid).limit(1)
        )
        r2 = (res2.data or []) if hasattr(res2, "data") else []
        if not r2:
            raise ValueError("Factura no encontrada tras finalizar")
        return dict(r2[0])

    async def finalizar_factura_verifactu(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
        usuario_id: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> FacturaOut:
        """
        Sellado VeriFactu extendido: cadena ``fingerprint``, URL SREI VeriFactu y bandera ``is_finalized``.
        Con ``DATABASE_URL``, transacción atómica y ``pg_advisory_xact_lock`` por empresa.
        """
        eid = _as_empresa_id_str(empresa_id)
        fid = int(factura_id)
        eng = get_engine()
        if eng is not None:
            row_out = await anyio.to_thread.run_sync(
                lambda: _pg_finalizar_factura_verifactu(empresa_id=eid, factura_id=fid)
            )
        else:
            row_out = await self._finalizar_factura_supabase_only(eid=eid, factura_id=fid)

        raw_nif_emisor = row_out.get("nif_emisor")
        if isinstance(raw_nif_emisor, str) and raw_nif_emisor.strip():
            row_out["nif_emisor"] = pii_crypto.decrypt_pii(raw_nif_emisor) or raw_nif_emisor

        try:
            await self._verifactu.generate_verifactu_qr(
                nif_emisor=str(row_out.get("nif_emisor") or ""),
                num_factura=str(row_out.get("num_factura") or row_out.get("numero_factura") or ""),
                fecha=_fecha_para_finalizar_iso(row_out),
                importe_total=float(row_out.get("total_factura") or 0.0),
                fingerprint=str(row_out.get("fingerprint") or ""),
                storage_path=f"{eid}/verifactu_qr/{fid}.png",
            )
        except Exception:
            pass

        await self._verifactu.registrar_evento(
            accion="FINALIZAR_FACTURA_VERIFACTU",
            registro_id=str(fid),
            detalles={
                "fingerprint": str(row_out.get("fingerprint") or "")[:32] + "…",
                "qr_code_url": str(row_out.get("qr_code_url") or "")[:120],
            },
            empresa_id=eid,
            usuario_id=usuario_id,
        )
        await self._audit.try_log(
            empresa_id=eid,
            accion="FINALIZAR_VERIFACTU",
            tabla="facturas",
            registro_id=str(fid),
            cambios={
                "fingerprint": (str(row_out.get("fingerprint") or "")[:24] + "…")
                if row_out.get("fingerprint")
                else None,
            },
        )

        cid = str(row_out.get("cliente") or "").strip()
        cli_det: ClienteOut | None = None
        if cid:
            try:
                rcli: Any = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes").select("*").eq("empresa_id", eid).eq("id", cid).limit(1)
                    )
                )
                crd: list[dict[str, Any]] = (rcli.data or []) if hasattr(rcli, "data") else []
                if crd:
                    if isinstance(crd[0].get("nif"), str) and crd[0].get("nif", "").strip():
                        crd0_nif = str(crd[0]["nif"])
                        crd[0]["nif"] = pii_crypto.decrypt_pii(crd0_nif) or crd0_nif
                    cli_det = ClienteOut(**crd[0])
            except Exception:
                cli_det = None

        row_merged = dict(row_out)
        raw_nif_emisor_merged = row_merged.get("nif_emisor")
        if isinstance(raw_nif_emisor_merged, str) and raw_nif_emisor_merged.strip():
            row_merged["nif_emisor"] = pii_crypto.decrypt_pii(raw_nif_emisor_merged) or raw_nif_emisor_merged
        row_merged = await self._enviar_aeat_tras_finalizar(empresa_id=eid, factura_row=row_merged)

        if background_tasks is not None:
            from app.services.webhook_service import EVENT_FACTURA_FINALIZADA, dispatch_webhook

            dispatch_webhook(
                empresa_id=eid,
                event_type=EVENT_FACTURA_FINALIZADA,
                payload={
                    "factura_id": fid,
                    "numero_factura": str(
                        row_merged.get("numero_factura") or row_merged.get("num_factura") or ""
                    ),
                    "is_finalized": bool(row_merged.get("is_finalized")),
                },
                background_tasks=background_tasks,
            )

        return FacturaOut.model_validate({**row_merged, "cliente_detalle": cli_det})

    async def _enviar_aeat_tras_finalizar(
        self,
        *,
        empresa_id: str,
        factura_row: dict[str, Any],
    ) -> dict[str, Any]:
        """Tras ``is_finalized``, remisión opcional a la AEAT si está habilitada en configuración."""
        if not factura_row.get("is_finalized"):
            return factura_row
        if not str(factura_row.get("fingerprint") or "").strip():
            return factura_row
        settings = get_settings()
        if not settings.AEAT_VERIFACTU_ENABLED:
            return factura_row
        try:
            fid = int(factura_row.get("id") or 0)
            if fid < 1:
                return factura_row
            return await send_to_aeat(
                self._db,
                invoice_id=fid,
                empresa_id=empresa_id,
                settings=settings,
            )
        except Exception:
            return factura_row

    async def reenviar_aeat_sif(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
        usuario_id: str | None = None,
    ) -> FacturaOut:
        """Reintenta el envío SIF a la AEAT (errores técnicos o rechazo corregible en certificado/URL)."""
        eid = _as_empresa_id_str(empresa_id)
        fid = int(factura_id)
        settings = get_settings()
        if not settings.AEAT_VERIFACTU_ENABLED:
            raise ValueError(
                "El envío a la AEAT está desactivado. Configure AEAT_VERIFACTU_ENABLED=1 en el servidor."
            )

        res: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", fid).eq("empresa_id", eid).limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Factura no encontrada")
        fr = dict(rows[0])
        if not fr.get("is_finalized"):
            raise ValueError("Solo se puede enviar a la AEAT una factura finalizada.")
        if not str(fr.get("fingerprint") or "").strip():
            raise ValueError("La factura no tiene huella fingerprint de registro.")
        cid = str(fr.get("cliente") or "").strip()
        cli_det: ClienteOut | None = None
        if cid:
            try:
                rcli: Any = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes").select("*").eq("empresa_id", eid).eq("id", cid).limit(1)
                    )
                )
                crd: list[dict[str, Any]] = (rcli.data or []) if hasattr(rcli, "data") else []
                if crd:
                    if isinstance(crd[0].get("nif"), str) and crd[0].get("nif", "").strip():
                        crd0_nif = str(crd[0]["nif"])
                        crd[0]["nif"] = pii_crypto.decrypt_pii(crd0_nif) or crd0_nif
                    cli_det = ClienteOut(**crd[0])
            except Exception:
                pass

        merged = await send_to_aeat(
            self._db,
            invoice_id=fid,
            empresa_id=eid,
            settings=settings,
        )
        raw_nif_emisor_merged = merged.get("nif_emisor")
        if isinstance(raw_nif_emisor_merged, str) and raw_nif_emisor_merged.strip():
            merged["nif_emisor"] = (
                pii_crypto.decrypt_pii(raw_nif_emisor_merged) or raw_nif_emisor_merged
            )
        await self._audit.try_log(
            empresa_id=eid,
            accion="REENVIAR_AEAT_SIF",
            tabla="facturas",
            registro_id=str(fid),
            cambios={"aeat_sif_estado": merged.get("aeat_sif_estado")},
        )
        return FacturaOut.model_validate({**merged, "cliente_detalle": cli_det})

    async def exportar_aeat_inspeccion_zip(self, *, empresa_id: str | UUID) -> tuple[bytes, str, int]:
        """
        Libro CSV + JSON con cadena de hashes VeriFactu, empaquetados en ZIP (inspección AEAT).
        Facturas ordenadas por fecha de emisión y número.
        Devuelve ``(zip_bytes, nombre_descarga, num_facturas)``.
        """
        eid = _as_empresa_id_str(empresa_id)
        res: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("empresa_id", eid)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        rows.sort(
            key=lambda r: (_fecha_emision_str(r), _numero_factura_str(r)),
        )

        cliente_ids = {
            str(r.get("cliente") or "").strip()
            for r in rows
            if r.get("cliente") is not None and str(r.get("cliente")).strip()
        }
        nif_por_cliente: dict[str, str] = {}
        if cliente_ids:
            try:
                qc = filter_not_deleted(
                    self._db.table("clientes")
                    .select("id,nif")
                    .eq("empresa_id", eid)
                    .in_("id", list(cliente_ids))
                )
                rc: Any = await self._db.execute(qc)
                for crow in (rc.data or []) if hasattr(rc, "data") else []:
                    cid = str(crow.get("id") or "").strip()
                    if cid:
                        raw_nif_cli = str(crow.get("nif") or "").strip()
                        nif_por_cliente[cid] = (
                            pii_crypto.decrypt_pii(raw_nif_cli) or raw_nif_cli
                        )
            except Exception:
                pass

        buf_csv = io.StringIO()
        w = csv.writer(buf_csv, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        w.writerow(
            [
                "numero",
                "fecha",
                "cliente_nif",
                "base_imponible",
                "cuota_iva",
                "total",
                "hash_verifactu",
            ]
        )
        cadena_registros: list[dict[str, Any]] = []
        cadena_hashes: list[str] = []
        for r in rows:
            cid = str(r.get("cliente") or "").strip()
            nif_cli = nif_por_cliente.get(cid, "")
            num = _numero_factura_str(r)
            fe = _fecha_emision_str(r)
            h = _hash_verifactu(r)
            base = float(r.get("base_imponible") or 0.0)
            cuota = float(r.get("cuota_iva") or 0.0)
            total = float(r.get("total_factura") or 0.0)
            w.writerow(
                [
                    num,
                    fe,
                    nif_cli,
                    f"{base:.2f}",
                    f"{cuota:.2f}",
                    f"{total:.2f}",
                    h,
                ]
            )
            rid = r.get("id")
            cadena_registros.append(
                {
                    "id": rid,
                    "numero": num,
                    "fecha": fe,
                    "hash_registro": h,
                    "hash_anterior": str(r.get("hash_anterior") or "").strip() or None,
                }
            )
            if h:
                cadena_hashes.append(h)

        generado = datetime.now(timezone.utc).isoformat()
        payload_json: dict[str, Any] = {
            "empresa_id": eid,
            "generado_utc": generado,
            "registros_orden_cronologico": cadena_registros,
            "cadena_hashes": cadena_hashes,
        }
        json_bytes = json.dumps(
            payload_json,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        csv_bytes = ("\ufeff" + buf_csv.getvalue()).encode("utf-8")

        label_emp = "Empresa"
        try:
            re: Any = await self._db.execute(
                self._db.table("empresas")
                .select("nombre_comercial,nif")
                .eq("id", eid)
                .limit(1)
            )
            erows: list[dict[str, Any]] = (re.data or []) if hasattr(re, "data") else []
            if erows:
                er = erows[0]
                label_emp = (
                    str(er.get("nombre_comercial") or "").strip()
                    or str(er.get("nif") or "").strip()
                    or "Empresa"
                )
        except Exception:
            pass

        safe = _safe_zip_label(label_emp)
        fecha_fn = datetime.now(timezone.utc).strftime("%Y%m%d")
        zip_name = f"Inspeccion_AEAT_{safe}_{fecha_fn}.zip"

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("libro_facturas_aeat.csv", csv_bytes)
            zf.writestr("cadena_hashes_verifactu.json", json_bytes)
        zip_buf.seek(0)
        return zip_buf.getvalue(), zip_name, len(rows)

    async def _eliminar_factura_compensacion(self, *, factura_id: int) -> None:
        """Best-effort: elimina factura insertada si falla el cierre del proceso (portes)."""
        try:
            await self._db.execute(self._db.table("facturas").delete().eq("id", factura_id))
        except Exception:
            pass

    async def generar_desde_portes(
        self,
        *,
        empresa_id: str | UUID,
        payload: FacturaCreateFromPortes,
        usuario_id: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> FacturaGenerateResult:
        """
        Genera factura desde portes pendientes con encadenamiento VeriFactu (SIF).

        1. **Encadenamiento**: ``obtener_ultimo_hash_y_secuencial(empresa_id)`` → ``hash_anterior``,
           ``siguiente_secuencial``.
        2. **Identidad**: ``nif_emisor`` desde ``empresas.nif``; NIF cliente desde ``clientes``.
        3. **Huella**: ``VerifactuService.generate_invoice_hash`` (cadena inmutable + ``hash_anterior``)
           → ``hash_registro`` / ``hash_factura``.
        4. **Persistencia** en ``facturas`` (``tipo_factura='F1'``, ``num_factura``, etc.).
        5. **Portes** (``schemas/porte.py``): tras insert OK, ``estado='facturado'`` y ``factura_id``.
        """
        eid = _as_empresa_id_str(empresa_id)
        cid = str(payload.cliente_id)
        # --- 1) Portes pendientes del cliente (opcionalmente filtrados por IDs) ---
        q_portes = filter_not_deleted(
            self._db.table("portes")
            .select(
                "id, fecha, origen, destino, descripcion, precio_pactado, bultos, km_estimados, peso_ton"
            )
            .eq("empresa_id", eid)
            .eq("estado", "pendiente")
            .eq("cliente_id", cid)
            .order("fecha", desc=False)
        )
        if payload.porte_ids is not None:
            if not payload.porte_ids:
                raise ValueError("Debe indicar al menos un porte o no enviar porte_ids")
            q_portes = q_portes.in_("id", [str(x) for x in payload.porte_ids])  # type: ignore[attr-defined]
        res_portes: Any = await self._db.execute(q_portes)
        portes_rows: list[dict[str, Any]] = (res_portes.data or []) if hasattr(res_portes, "data") else []
        if not portes_rows:
            raise ValueError("No hay portes pendientes para ese cliente")
        if payload.porte_ids is not None:
            found = {str(r.get("id")) for r in portes_rows if r.get("id") is not None}
            wanted = {str(x).strip() for x in payload.porte_ids if str(x).strip()}
            if found != wanted:
                raise ValueError(
                    "Algunos portes no existen, no están pendientes o no pertenecen a este cliente"
                )

        portes_ids = [str(r["id"]) for r in portes_rows if r.get("id") is not None]
        if not portes_ids:
            raise ValueError("Portes sin identificador válido")

        require_non_negative_precio_pactado(portes_rows)
        items_m = [
            {
                "cantidad": Decimal("1"),
                "precio_unitario": to_decimal(r.get("precio_pactado") or 0),
                "tipo_iva_porcentaje": quantize_financial(payload.iva_porcentaje),
            }
            for r in portes_rows
        ]
        inv_tot = MathEngine.calculate_totals(items_m)
        base_dec = inv_tot.base_imponible_total
        cuota_dec = inv_tot.cuota_iva_total
        total_dec = inv_tot.total_factura
        base_imponible = float(decimal_to_db_numeric(base_dec))
        cuota_iva = float(decimal_to_db_numeric(cuota_dec))
        total_factura = float(decimal_to_db_numeric(total_dec))

        # Valores congelados en factura (motor matemático / fiscal): independientes del porte tras emitir
        porte_lineas_snapshot: list[dict[str, Any]] = []
        km_acum = Decimal("0")
        for r in portes_rows:
            km = round_fiat(r.get("km_estimados") or 0)
            precio = round_fiat(r.get("precio_pactado") or 0)
            km_acum += km
            porte_lineas_snapshot.append(
                {
                    "porte_id": str(r.get("id") or ""),
                    "precio_pactado": float(precio),
                    "km_estimados": float(km),
                    "fecha": str(r.get("fecha") or ""),
                    "origen": str(r.get("origen") or ""),
                    "destino": str(r.get("destino") or ""),
                    "descripcion": r.get("descripcion"),
                    "bultos": r.get("bultos"),
                }
            )
        total_km_estimados_snapshot = float(round_fiat(km_acum))
        fecha_emision = date.today()
        fecha_iso = fecha_emision.isoformat()

        # --- 2) NIF emisor (empresa) y NIF cliente (receptor del porte / pedido) ---
        nif_emisor = ""
        nif_cliente = ""
        empresa_row: dict[str, Any] = {}
        cliente_row: dict[str, Any] = {}
        try:
            res_nif_emp: Any = await self._db.execute(
                self._db.table("empresas").select("nif,nombre_comercial,nombre_legal").eq("id", eid).limit(1)
            )
            erows: list[dict[str, Any]] = (res_nif_emp.data or []) if hasattr(res_nif_emp, "data") else []
            if erows:
                empresa_row = dict(erows[0])
                raw_nif_emp = str(empresa_row.get("nif") or "").strip()
                nif_emisor = pii_crypto.decrypt_pii(raw_nif_emp) or raw_nif_emp
        except Exception:
            pass
        try:
            res_nif_cli: Any = await self._db.execute(
                self._db.table("clientes").select("nif,nombre").eq("id", cid).limit(1)
            )
            crows: list[dict[str, Any]] = (res_nif_cli.data or []) if hasattr(res_nif_cli, "data") else []
            if crows:
                cliente_row = dict(crows[0])
                raw_nif_cli = str(cliente_row.get("nif") or "").strip()
                nif_cliente = pii_crypto.decrypt_pii(raw_nif_cli) or raw_nif_cli
        except Exception:
            pass

        # --- 3) Eslabón anterior VeriFactu: hash encadenado + siguiente secuencial ---
        try:
            eslabon = await self._verifactu.obtener_ultimo_hash_y_secuencial(empresa_id=eid)
        except Exception as e:
            raise RuntimeError(
                f"No se pudo obtener el eslabón anterior VeriFactu para la empresa: {e}"
            ) from e

        serie = os.getenv("VERIFACTU_SERIE_FACTURA", "FAC").strip() or "FAC"
        anio = fecha_emision.year
        # Serie-Año-Secuencial (identificador de factura en cadena VeriFactu)
        num_fact = f"{serie}-{anio}-{eslabon.siguiente_secuencial:06d}"

        # --- 4) Huella de inalterabilidad: hash_factura único encadenado (génesis o hash anterior)
        try:
            hash_registro = VerifactuService.generate_invoice_hash(
                {
                    "num_factura": num_fact,
                    "fecha_emision": fecha_iso,
                    "nif_emisor": nif_emisor,
                    "total_factura": float(total_factura),
                },
                eslabon.hash_anterior,
            )
        except Exception as e:
            raise ValueError(
                f"Encadenamiento criptográfico VeriFactu: no se pudo generar el hash de registro: {e}"
            ) from e

        previous_fingerprint = await self._get_last_fingerprint_hash(empresa_id=eid)
        fingerprint_hash = compute_invoice_fingerprint(
            {
                "nif_emisor": nif_emisor,
                "nif_receptor": nif_cliente,
                "numero_factura": num_fact,
                "fecha_emision": fecha_iso,
                "total_factura": float(total_factura),
            },
            previous_fingerprint,
        )
        previous_invoice_hash = previous_fingerprint
        qr_verifactu = await self._verifactu.generate_verifactu_qr(
            nif_emisor=nif_emisor,
            num_factura=num_fact,
            fecha=fecha_iso,
            importe_total=float(total_factura),
            fingerprint=hash_registro,
            huella_hash=hash_registro,
            storage_bucket=None,
        )
        qr_content = str(qr_verifactu.get("verification_url") or "").strip() or None

        # Campos alineados con VeriFactu / SIF (tipo F1, huella y encadenamiento)
        factura_payload: dict[str, Any] = {
            "empresa_id": eid,
            "cliente": cid,
            "tipo_factura": "F1",
            "num_factura": num_fact,
            "numero_factura": num_fact,
            "nif_emisor": pii_crypto.encrypt_pii(nif_emisor),
            "total_factura": total_factura,
            "base_imponible": base_imponible,
            "cuota_iva": cuota_iva,
            "fecha_emision": fecha_iso,
            "numero_secuencial": eslabon.siguiente_secuencial,
            "hash_anterior": eslabon.hash_anterior,
            "hash_registro": hash_registro,
            "hash_factura": hash_registro,
            "huella_anterior": eslabon.hash_anterior,
            "huella_hash": hash_registro,
            "fecha_hitos_verifactu": datetime.now(timezone.utc).isoformat(),
            "qr_content": qr_content,
            "qr_code_url": qr_content,
            "fingerprint_hash": fingerprint_hash,
            "previous_fingerprint": previous_fingerprint,
            "previous_invoice_hash": previous_invoice_hash,
            "bloqueado": True,
            "is_finalized": False,
            "porte_lineas_snapshot": porte_lineas_snapshot,
            "total_km_estimados_snapshot": total_km_estimados_snapshot,
            "estado_cobro": "emitida",
            "payment_status": "PENDING",
        }
        try:
            factura_payload["xml_verifactu"] = generar_xml_alta_factura(
                factura_payload,
                {
                    "nif": nif_emisor,
                    "nombre_comercial": str(empresa_row.get("nombre_comercial") or ""),
                    "nombre_legal": str(empresa_row.get("nombre_legal") or ""),
                },
                {
                    "nif": nif_cliente,
                    "nombre": str(cliente_row.get("nombre") or ""),
                },
                hash_registro,
            )
        except Exception as xml_err:
            raise RuntimeError(
                "VeriFactu: no se pudo generar el XML de alta de factura. "
                f"Detalle: {xml_err}"
            ) from xml_err

        factura_id: int | None = None
        factura_row: dict[str, Any] | None = None

        try:
            try:
                res_fact: Any = await self._db.execute(
                    self._db.table("facturas").insert(factura_payload)
                )
            except Exception as insert_err:
                raise RuntimeError(
                    "No se pudo insertar la factura VeriFactu "
                    "(tipo_factura, num_factura, nif_emisor, hash_registro, hash_anterior, "
                    "numero_secuencial, total_factura, …). "
                    "Revise el esquema de `facturas` y el error subyacente."
                ) from insert_err

            fact_rows: list[dict[str, Any]] = (res_fact.data or []) if hasattr(res_fact, "data") else []
            if not fact_rows:
                raise RuntimeError("Supabase insert factura returned no rows")
            factura_row = fact_rows[0]
            factura_id = _factura_pk(factura_row.get("id"))

            await self._verifactu.registrar_evento(
                accion="GENERAR_FACTURA_VERIFACTU",
                registro_id=str(factura_id),
                detalles={
                    "num_factura": num_fact,
                    "hash_registro": hash_registro,
                },
                empresa_id=eid,
                usuario_id=usuario_id,
            )

            # Portes: estado facturado + vínculo; Enterprise: persiste `co2_emitido` (huella ESG).
            plan_f = await fetch_empresa_plan(self._db, empresa_id=eid)
            enterprise = normalize_plan(plan_f) == PLAN_ENTERPRISE
            for pr in portes_rows:
                pid = str(pr.get("id") or "").strip()
                if not pid:
                    continue
                upd: dict[str, Any] = {"estado": "facturado", "factura_id": factura_id}
                if enterprise:
                    upd["co2_emitido"] = co2_emitido_desde_porte_row(dict(pr))
                await self._db.execute(
                    self._db.table("portes").update(upd).eq("empresa_id", eid).eq("id", pid)
                )

        except Exception:
            if factura_id is not None:
                await self._eliminar_factura_compensacion(factura_id=factura_id)
            raise

        assert factura_row is not None

        factura_row_out = dict(factura_row)
        raw_nif_emisor_out = factura_row_out.get("nif_emisor")
        if isinstance(raw_nif_emisor_out, str) and raw_nif_emisor_out.strip():
            factura_row_out["nif_emisor"] = (
                pii_crypto.decrypt_pii(raw_nif_emisor_out) or raw_nif_emisor_out
            )

        cli_det: ClienteOut | None = None
        try:
            rcli: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("clientes").select("*").eq("empresa_id", eid).eq("id", cid).limit(1)
                )
            )
            crd: list[dict[str, Any]] = (rcli.data or []) if hasattr(rcli, "data") else []
            if crd:
                if isinstance(crd[0].get("nif"), str) and crd[0].get("nif", "").strip():
                    crd0_nif = str(crd[0]["nif"])
                    crd[0]["nif"] = pii_crypto.decrypt_pii(crd0_nif) or crd0_nif
                cli_det = ClienteOut(**crd[0])
        except Exception:
            cli_det = None

        factura_out = FacturaOut.model_validate(
            {**factura_row_out, "cliente_detalle": cli_det}
        )

        await self._audit.try_log(
            empresa_id=eid,
            accion="GENERAR_FACTURA",
            tabla="facturas",
            registro_id=str(factura_id),
            cambios={
                "cliente_id": cid,
                "portes_ids": portes_ids,
                "numero_factura": str(factura_row.get("numero_factura") or num_fact),
                "total_factura": float(factura_row.get("total_factura") or total_factura),
                "numero_secuencial": eslabon.siguiente_secuencial,
                "hash_registro": hash_registro[:32] + "…",
            },
        )

        if background_tasks is not None:
            from app.services.webhook_service import EVENT_PORTE_FACTURADO, dispatch_webhook

            dispatch_webhook(
                empresa_id=eid,
                event_type=EVENT_PORTE_FACTURADO,
                payload={
                    "factura_id": factura_id,
                    "porte_ids": portes_ids,
                    "cliente_id": cid,
                    "estado": "facturado",
                },
                background_tasks=background_tasks,
            )

        # --- PDF (no bloquea integridad contable) ---
        pdf_base64: str | None = None
        pdf_storage_path: str | None = None
        try:
            res_emp: Any = await self._db.execute(
                self._db.table("empresas").select("nombre_comercial, nif").eq("id", eid).limit(1)
            )
            emp_rows: list[dict[str, Any]] = (res_emp.data or []) if hasattr(res_emp, "data") else []
            emp = emp_rows[0] if emp_rows else {}

            res_cli: Any = await self._db.execute(
                self._db.table("clientes").select("nombre, nif").eq("id", cid).limit(1)
            )
            cli_rows: list[dict[str, Any]] = (res_cli.data or []) if hasattr(res_cli, "data") else []
            cli = cli_rows[0] if cli_rows else {}

            emp_nif_plain = ""
            if isinstance(emp.get("nif"), str) and emp.get("nif", "").strip():
                emp_nif_plain = pii_crypto.decrypt_pii(emp.get("nif")) or str(emp.get("nif") or "")

            cli_nif_plain = ""
            if isinstance(cli.get("nif"), str) and cli.get("nif", "").strip():
                cli_nif_plain = pii_crypto.decrypt_pii(cli.get("nif")) or str(cli.get("nif") or "")

            conceptos: list[dict[str, Any]] = []
            for line in porte_lineas_snapshot:
                nombre = f"{line.get('fecha', '')} {line.get('origen', '')} → {line.get('destino', '')}"
                if line.get("descripcion"):
                    nombre += f" | {line.get('descripcion')}"
                conceptos.append(
                    {"nombre": nombre[:120], "precio": float(line.get("precio_pactado") or 0.0)}
                )

            qr_vf_b64 = generar_qr_verifactu(
                nif_emisor=str(emp_nif_plain or nif_emisor or "").strip(),
                num_factura=str(factura_row.get("numero_factura") or factura_row.get("num_factura") or num_fact),
                fecha=str(factura_row.get("fecha_emision") or fecha_iso),
                importe_total=float(factura_row.get("total_factura") or total_factura),
                legacy_path=True,
            )
            datos_empresa = {
                "nombre": str(emp.get("nombre_comercial") or "AB Logistics"),
                "nif": str(emp_nif_plain or ""),
                "hash": str(
                    factura_row.get("hash_registro")
                    or factura_row.get("hash_factura")
                    or hash_registro
                ),
                "numero_factura": str(factura_row.get("numero_factura") or num_fact),
                "num_factura": str(factura_row.get("num_factura") or num_fact),
                "fecha_emision": str(factura_row.get("fecha_emision") or fecha_iso),
                "base_imponible": float(factura_row.get("base_imponible") or base_imponible),
                "cuota_iva": float(factura_row.get("cuota_iva") or cuota_iva),
                "total_factura": float(factura_row.get("total_factura") or total_factura),
                "iva_porcentaje": float(payload.iva_porcentaje),
                "qr_verifactu_base64": qr_vf_b64,
            }
            datos_cliente = {
                "nombre": str(cli.get("nombre") or cid),
                "id": cid,
                "nif": str(cli_nif_plain or "").strip() or None,
            }

            pdf_base64 = await generar_pdf_factura_base64(
                datos_empresa=datos_empresa,
                datos_cliente=datos_cliente,
                conceptos=conceptos,
            )

            try:
                import base64 as _b64

                pdf_bytes = _b64.b64decode(pdf_base64.encode("ascii"))
                path = f"{eid}/{factura_out.numero_factura}.pdf"
                await self._db.storage_upload(
                    bucket="facturas",
                    path=path,
                    content=pdf_bytes,
                    content_type="application/pdf",
                )
                pdf_storage_path = path
            except Exception:
                pdf_storage_path = None
        except Exception:
            pdf_base64 = None
            pdf_storage_path = None

        return FacturaGenerateResult(
            factura=factura_out,
            portes_facturados=[UUID(x) for x in portes_ids],
            pdf_base64=pdf_base64,
            pdf_storage_path=pdf_storage_path,
        )

    async def emitir_factura_rectificativa(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
        motivo: str,
        usuario_id: str | None = None,
    ) -> FacturaOut:
        """
        Emite una factura rectificativa **R1** que anula en importes una F1 sellada (VeriFactu).

        - Importes en **negativo** (base, cuota IVA, total).
        - ``porte_lineas_snapshot`` clonado con ``precio_pactado`` negado (inmutabilidad).
        - ``hash_anterior`` del registro R1 = ``hash_registro`` de la **factura rectificada** (F1).
        - ``numero_secuencial`` = siguiente global de la cadena de empresa.
        - Huella: incluye ``tipo_factura=R1`` y referencia ``|RECT:`` al número de la original [cite: 2026-03-22].
        """
        eid = _as_empresa_id_str(empresa_id)
        fid = int(factura_id)
        if not eid or fid < 1:
            raise ValueError("empresa_id y factura_id son obligatorios")

        res_o: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", fid).eq("empresa_id", eid).limit(1)
        )
        o_rows: list[dict[str, Any]] = (res_o.data or []) if hasattr(res_o, "data") else []
        if not o_rows:
            raise ValueError("Factura original no encontrada")
        orig = dict(o_rows[0])

        tipo = str(orig.get("tipo_factura") or "").strip().upper()
        if tipo != "F1":
            raise ValueError("Solo se pueden rectificar facturas tipo F1")

        hash_original = str(
            orig.get("hash_registro") or orig.get("hash_factura") or ""
        ).strip()
        if not hash_original:
            raise ValueError("La factura original no está sellada (sin hash_registro)")

        res_dup: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id")
            .eq("empresa_id", eid)
            .eq("factura_rectificada_id", fid)
            .limit(1)
        )
        if (res_dup.data or []) if hasattr(res_dup, "data") else []:
            raise ValueError("Ya existe una rectificativa emitida para esta factura")

        eslabon = await self._verifactu.obtener_ultimo_hash_y_secuencial(empresa_id=eid)
        siguiente_seq = eslabon.siguiente_secuencial

        fecha_emision = date.today()
        fecha_iso = fecha_emision.isoformat()

        base_r_dec = negate_fiat_for_rectificativa(orig.get("base_imponible"))
        cuota_r_dec = negate_fiat_for_rectificativa(orig.get("cuota_iva"))
        total_orig_dec = round_fiat(orig.get("total_factura") or 0)
        if total_orig_dec == 0 and (base_r_dec != 0 or cuota_r_dec != 0):
            total_r_dec = round_fiat(base_r_dec + cuota_r_dec)
        else:
            total_r_dec = negate_fiat_for_rectificativa(orig.get("total_factura"))
        base_r = float(base_r_dec)
        cuota_r = float(cuota_r_dec)
        total_r = float(total_r_dec)

        nif_emisor_raw = str(orig.get("nif_emisor") or "").strip()
        nif_emisor = pii_crypto.decrypt_pii(nif_emisor_raw) or nif_emisor_raw
        if not nif_emisor:
            try:
                res_ne: Any = await self._db.execute(
                    self._db.table("empresas").select("nif").eq("id", eid).limit(1)
                )
                ner: list[dict[str, Any]] = (res_ne.data or []) if hasattr(res_ne, "data") else []
                if ner:
                    raw_nif_emp = str(ner[0].get("nif") or "").strip()
                    nif_emisor = pii_crypto.decrypt_pii(raw_nif_emp) or raw_nif_emp
            except Exception:
                pass

        cliente_id = str(orig.get("cliente") or "").strip()
        nif_cliente = ""
        cliente_nombre_r1 = ""
        if cliente_id:
            try:
                res_nc: Any = await self._db.execute(
                    self._db.table("clientes").select("nif,nombre").eq("id", cliente_id).limit(1)
                )
                ncr: list[dict[str, Any]] = (res_nc.data or []) if hasattr(res_nc, "data") else []
                if ncr:
                    raw_nif_cli = str(ncr[0].get("nif") or "").strip()
                    nif_cliente = pii_crypto.decrypt_pii(raw_nif_cli) or raw_nif_cli
                    cliente_nombre_r1 = str(ncr[0].get("nombre") or "").strip()
            except Exception:
                pass

        num_orig = str(
            orig.get("num_factura") or orig.get("numero_factura") or ""
        ).strip()
        if not num_orig:
            raise ValueError("La factura original no tiene número VeriFactu (num_factura)")

        serie_r = os.getenv("VERIFACTU_SERIE_RECTIFICATIVA", "R").strip() or "R"
        anio = fecha_emision.year
        num_fact_r = f"{serie_r}-{anio}-{siguiente_seq:06d}"

        hash_registro = VerifactuService.generate_invoice_hash(
            {
                "num_factura": num_fact_r,
                "fecha_emision": fecha_iso,
                "nif_emisor": nif_emisor,
                "total_factura": float(total_r),
            },
            eslabon.hash_anterior,
        )

        previous_fingerprint = await self._get_last_fingerprint_hash(empresa_id=eid)
        fingerprint_hash = compute_invoice_fingerprint(
            {
                "nif_emisor": nif_emisor,
                "nif_receptor": nif_cliente,
                "numero_factura": num_fact_r,
                "fecha_emision": fecha_iso,
                "total_factura": float(total_r),
            },
            previous_fingerprint,
        )
        previous_invoice_hash = previous_fingerprint
        qr_verifactu = await self._verifactu.generate_verifactu_qr(
            nif_emisor=nif_emisor,
            num_factura=num_fact_r,
            fecha=fecha_iso,
            importe_total=float(total_r),
            fingerprint=hash_registro,
            huella_hash=hash_registro,
            storage_bucket=None,
        )
        qr_content = str(qr_verifactu.get("verification_url") or "").strip() or None

        porte_snap = _clone_snapshot_con_importes_negativos(orig.get("porte_lineas_snapshot"))
        km_snap = orig.get("total_km_estimados_snapshot")
        try:
            km_val = float(km_snap) if km_snap is not None else 0.0
        except (TypeError, ValueError):
            km_val = 0.0

        factura_payload: dict[str, Any] = {
            "empresa_id": eid,
            "cliente": cliente_id,
            "tipo_factura": "R1",
            "num_factura": num_fact_r,
            "numero_factura": num_fact_r,
            "nif_emisor": pii_crypto.encrypt_pii(nif_emisor),
            "total_factura": total_r,
            "base_imponible": base_r,
            "cuota_iva": cuota_r,
            "fecha_emision": fecha_iso,
            "numero_secuencial": siguiente_seq,
            "hash_anterior": eslabon.hash_anterior,
            "hash_registro": hash_registro,
            "hash_factura": hash_registro,
            "huella_anterior": eslabon.hash_anterior,
            "huella_hash": hash_registro,
            "fecha_hitos_verifactu": datetime.now(timezone.utc).isoformat(),
            "qr_content": qr_content,
            "qr_code_url": qr_content,
            "fingerprint_hash": fingerprint_hash,
            "previous_fingerprint": previous_fingerprint,
            "previous_invoice_hash": previous_invoice_hash,
            "bloqueado": True,
            "is_finalized": False,
            "porte_lineas_snapshot": porte_snap,
            "total_km_estimados_snapshot": km_val,
            "factura_rectificada_id": fid,
            "motivo_rectificacion": str(motivo).strip(),
            "estado_cobro": "emitida",
            "payment_status": "PENDING",
        }
        emp_row_r1: dict[str, Any] = {}
        try:
            res_emp_r1: Any = await self._db.execute(
                self._db.table("empresas").select("nif,nombre_comercial,nombre_legal").eq("id", eid).limit(1)
            )
            er_emp: list[dict[str, Any]] = (res_emp_r1.data or []) if hasattr(res_emp_r1, "data") else []
            if er_emp:
                emp_row_r1 = dict(er_emp[0])
        except Exception:
            pass
        try:
            factura_payload["xml_verifactu"] = generar_xml_alta_factura(
                factura_payload,
                {
                    "nif": nif_emisor,
                    "nombre_comercial": str(emp_row_r1.get("nombre_comercial") or ""),
                    "nombre_legal": str(emp_row_r1.get("nombre_legal") or ""),
                },
                {"nif": nif_cliente, "nombre": cliente_nombre_r1},
                hash_registro,
            )
        except Exception as xml_err:
            raise RuntimeError(
                "VeriFactu: no se pudo generar el XML de la rectificativa R1. "
                f"Detalle: {xml_err}"
            ) from xml_err

        res_ins: Any = await self._db.execute(self._db.table("facturas").insert(factura_payload))
        ins_rows: list[dict[str, Any]] = (res_ins.data or []) if hasattr(res_ins, "data") else []
        if not ins_rows:
            raise RuntimeError("No se pudo insertar la rectificativa R1")
        row_new = dict(ins_rows[0])
        new_id = _factura_pk(row_new.get("id"))

        await self._verifactu.registrar_evento(
            accion="EMITIR_RECTIFICATIVA_R1",
            registro_id=str(new_id),
            detalles={
                "num_factura": num_fact_r,
                "hash_registro": hash_registro,
                "factura_rectificada_id": fid,
                "num_factura_rectificada": num_orig,
                "motivo": str(motivo).strip()[:500],
            },
            empresa_id=eid,
            usuario_id=usuario_id,
        )

        await self._audit.try_log(
            empresa_id=eid,
            accion="RECTIFICATIVA_R1",
            tabla="facturas",
            registro_id=str(new_id),
            cambios={
                "factura_rectificada_id": fid,
                "numero_factura": num_fact_r,
                "total_factura": total_r,
                "motivo": str(motivo).strip()[:500],
            },
        )

        # Si la rectificación afecta una factura de un mes anterior, fuerza recálculo del snapshot
        # financiero de ese periodo (consistencia KPI histórica).
        orig_period = str(orig.get("fecha_emision") or "")[:7]
        current_period = date.today().strftime("%Y-%m")
        if len(orig_period) == 7 and orig_period != current_period:
            try:
                await self._db.rpc(
                    "_upsert_monthly_kpis",
                    {"p_empresa_id": eid, "p_period_month": orig_period},
                )
            except Exception:
                # Best effort: no bloquear emisión fiscal por mantenimiento de snapshot.
                pass

        raw_nif_emisor_new = row_new.get("nif_emisor")
        if isinstance(raw_nif_emisor_new, str) and raw_nif_emisor_new.strip():
            row_new["nif_emisor"] = (
                pii_crypto.decrypt_pii(raw_nif_emisor_new) or raw_nif_emisor_new
            )

        return FacturaOut(**row_new)

    async def get_factura_pdf_data(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
    ) -> FacturaPdfDataOut:
        """
        Datos estructurados + QR VeriFactu (URL SREI) en Base64 para PDF comercial en cliente.
        Totales alineados con ``round_fiat`` / ``safe_divide`` (Math Engine).
        Metadatos AEAT: último ``verifactu_envios.csv_aeat`` si existe; la URL del QR prioriza
        ``qr_code_url`` de la factura o se reconstruye con ``build_srei_verifactu_url``.
        """
        eid = _as_empresa_id_str(empresa_id)
        fid = int(factura_id)
        if not eid or fid < 1:
            raise ValueError("Factura no encontrada")

        res_f: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", fid).eq("empresa_id", eid).limit(1)
        )
        fr_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        if not fr_rows:
            raise ValueError("Factura no encontrada")
        fr = dict(fr_rows[0])

        emp_row: dict[str, Any] = {}
        try:
            res_e: Any = await self._db.execute(
                self._db.table("empresas")
                .select("nif,nombre_comercial,nombre_legal,direccion")
                .eq("id", eid)
                .limit(1)
            )
            er = (res_e.data or []) if hasattr(res_e, "data") else []
            if er:
                emp_row = dict(er[0])
        except Exception:
            pass

        cid = str(fr.get("cliente") or "").strip()
        cli_row: dict[str, Any] = {}
        if cid:
            try:
                res_c: Any = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes")
                        .select("nombre,nif")
                        .eq("empresa_id", eid)
                        .eq("id", cid)
                        .limit(1)
                    )
                )
                cr = (res_c.data or []) if hasattr(res_c, "data") else []
                if cr:
                    cli_row = dict(cr[0])
            except Exception:
                pass

        nombre_em = str(
            emp_row.get("nombre_comercial") or emp_row.get("nombre_legal") or "Emisor"
        ).strip()
        nif_source = fr.get("nif_emisor") or emp_row.get("nif") or ""
        nif_em = (
            pii_crypto.decrypt_pii(str(nif_source).strip())
            or str(nif_source).strip()
        ).strip()

        lineas_out: list[FacturaPdfLineaOut] = []
        for line in _parse_porte_lineas_snapshot(fr.get("porte_lineas_snapshot")):
            orig = str(line.get("origen") or "").strip()
            dst = str(line.get("destino") or "").strip()
            desc = str(line.get("descripcion") or "").strip()
            concepto = desc or (f"{orig} → {dst}" if (orig or dst) else "Servicio de transporte")
            precio = float(round_fiat(line.get("precio_pactado")))
            lineas_out.append(
                FacturaPdfLineaOut(
                    concepto=concepto[:500],
                    cantidad=1.0,
                    precio_unitario=precio,
                    importe=precio,
                )
            )

        base_dec = round_fiat(fr.get("base_imponible"))
        cuota_dec = round_fiat(fr.get("cuota_iva"))
        total_dec = round_fiat(fr.get("total_factura"))
        if base_dec == Decimal("0"):
            iva_pct = 0.0
        else:
            iva_pct = float(safe_divide(cuota_dec * Decimal("100"), base_dec))

        base_f = as_float_fiat(base_dec)
        cuota_f = as_float_fiat(cuota_dec)
        total_f = as_float_fiat(total_dec)

        fp_full = str(fr.get("fingerprint") or "").strip() or None
        hr_full = str(fr.get("hash_registro") or fr.get("hash_factura") or "").strip() or None
        chain_for_audit = (fp_full or hr_full or "").strip()
        if len(chain_for_audit) <= 16:
            audit = chain_for_audit
        else:
            audit = f"{chain_for_audit[:8]}…{chain_for_audit[-8:]}"

        num_vf = str(fr.get("num_factura") or fr.get("numero_factura") or "").strip() or None
        fe_str = _fecha_emision_str(fr)

        res_v: Any = await self._db.execute(
            self._db.table("verifactu_envios")
            .select("csv_aeat,estado,created_at")
            .eq("empresa_id", eid)
            .eq("factura_id", fid)
            .order("created_at", desc=True)
            .limit(1)
        )
        vr = (res_v.data or []) if hasattr(res_v, "data") else []
        aeat_csv: str | None = None
        if vr and vr[0].get("csv_aeat") is not None:
            aeat_csv = str(vr[0]["csv_aeat"]).strip() or None

        qr_url = str(fr.get("qr_code_url") or "").strip() or None
        if not qr_url:
            nif_e = nif_em
            num_s = str(fr.get("num_factura") or fr.get("numero_factura") or "").strip()
            if nif_e and num_s and fe_str:
                qr_url = build_srei_verifactu_url(
                    nif_e,
                    num_s,
                    fe_str,
                    total_f,
                    huella_hash=hr_full or fp_full,
                )
        if not qr_url and aeat_csv and aeat_csv.lower().startswith("http"):
            qr_url = aeat_csv

        qr_b64 = ""
        if qr_url:
            try:
                raw_png = qr_png_bytes_from_url(qr_url)
                qr_b64 = base64.b64encode(raw_png).decode("ascii")
            except Exception:
                qr_b64 = ""

        fecha_raw = fr.get("fecha_emision")
        if isinstance(fecha_raw, datetime):
            fecha_d = fecha_raw.date()
        elif isinstance(fecha_raw, date):
            fecha_d = fecha_raw
        else:
            try:
                fecha_d = date.fromisoformat(str(fecha_raw)[:10])
            except (TypeError, ValueError):
                fecha_d = date.today()

        return FacturaPdfDataOut(
            factura_id=fid,
            numero_factura=str(fr.get("numero_factura") or fr.get("num_factura") or str(fid)),
            num_factura_verifactu=num_vf,
            tipo_factura=str(fr.get("tipo_factura") or "").strip() or None,
            fecha_emision=fecha_d,
            emisor=FacturaPdfEmisorOut(
                nombre=nombre_em,
                nif=nif_em,
                direccion=str(emp_row.get("direccion") or "").strip() or None,
            ),
            receptor=FacturaPdfReceptorOut(
                nombre=str(cli_row.get("nombre") or "Cliente").strip(),
                nif=str(cli_row.get("nif") or "").strip() or None,
            ),
            lineas=lineas_out,
            base_imponible=base_f,
            tipo_iva_porcentaje=iva_pct,
            cuota_iva=cuota_f,
            total_factura=total_f,
            verifactu_qr_base64=qr_b64,
            verifactu_validation_url=qr_url,
            verifactu_hash_audit=audit,
            fingerprint_completo=fp_full,
            hash_registro=hr_full,
            aeat_csv_ultimo_envio=aeat_csv,
        )

    async def generate_factura_pdf_bytes(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
    ) -> bytes:
        pdf_data = await self.get_factura_pdf_data(empresa_id=empresa_id, factura_id=factura_id)
        return await anyio.to_thread.run_sync(_factura_pdf_data_to_pdf_bytes, pdf_data)

    async def resolve_destinatario_email_factura(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
    ) -> tuple[str, str]:
        """
        Número de factura legible + email del cliente (maestro ``clientes.email``).
        ``ValueError`` si no hay factura, cliente o email utilizable.
        """
        eid = _as_empresa_id_str(empresa_id)
        fid = int(factura_id)
        if not eid or fid < 1:
            raise ValueError("Factura no encontrada")
        res_f: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id,numero_factura,num_factura,cliente")
            .eq("id", fid)
            .eq("empresa_id", eid)
            .limit(1)
        )
        fr_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        if not fr_rows:
            raise ValueError("Factura no encontrada")
        fr = dict(fr_rows[0])
        cid = str(fr.get("cliente") or "").strip()
        if not cid:
            raise ValueError("Factura sin cliente asociado")
        res_c: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("clientes")
                .select("email,nombre")
                .eq("empresa_id", eid)
                .eq("id", cid)
                .limit(1)
            )
        )
        cr = (res_c.data or []) if hasattr(res_c, "data") else []
        if not cr:
            raise ValueError("Cliente no encontrado")
        email_raw = str(cr[0].get("email") or "").strip()
        if not email_raw or "@" not in email_raw:
            raise ValueError("El cliente no tiene un email válido para el envío")
        num = str(fr.get("numero_factura") or fr.get("num_factura") or str(fid)).strip()
        return num, email_raw.lower()

    async def list_facturas_for_cliente(
        self,
        *,
        empresa_id: str | UUID,
        cliente_id: str | UUID,
    ) -> list[dict[str, Any]]:
        eid = _as_empresa_id_str(empresa_id)
        cid = str(cliente_id).strip()
        if not eid or not cid:
            return []
        res_f: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id,numero_factura,fecha_emision,total_factura,estado_cobro,cliente")
            .eq("empresa_id", eid)
            .eq("cliente", cid)
            .order("fecha_emision", desc=True)
        )
        rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        return [dict(r) for r in rows]

    async def recalculate_invoice(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: int,
        global_discount: Decimal = Decimal("0"),
        aplicar_recargo_equivalencia: bool = False,
    ) -> FacturaRecalculateOut:
        """
        Recalcula base / IVA / total desde ``porte_lineas_snapshot`` con :class:`MathEngine`
        (Decimal, ROUND_HALF_UP). No persiste cambios.

        Bloqueado si existe ``hash_factura`` o ``hash_registro`` (cadena VeriFactu).
        """
        eid = _as_empresa_id_str(empresa_id)
        fid = int(factura_id)
        if fid < 1:
            raise ValueError("Factura no encontrada")

        res_f: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", fid).eq("empresa_id", eid).limit(1)
        )
        fr_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        if not fr_rows:
            raise ValueError("Factura no encontrada")
        fr = dict(fr_rows[0])

        if str(fr.get("hash_factura") or "").strip() or str(fr.get("hash_registro") or "").strip():
            raise ValueError(
                "La factura tiene huella VeriFactu (hash_factura / hash_registro). "
                "No se recalculan totales para preservar la cadena de inalterabilidad."
            )

        lines = _parse_porte_lineas_snapshot(fr.get("porte_lineas_snapshot"))
        if not lines:
            raise ValueError("Factura sin líneas en porte_lineas_snapshot")

        base_o = to_decimal(fr.get("base_imponible") or 0)
        cuota_o = to_decimal(fr.get("cuota_iva") or 0)
        if base_o > 0 and cuota_o >= 0:
            iva_pct = quantize_financial(cuota_o / base_o * Decimal("100"))
        else:
            iva_pct = Decimal("21.00")

        items: list[dict[str, Any]] = []
        for ln in lines:
            items.append(
                {
                    "cantidad": Decimal("1"),
                    "precio_unitario": to_decimal(ln.get("precio_pactado") or 0),
                    "tipo_iva_porcentaje": iva_pct,
                }
            )

        tot = MathEngine.calculate_totals(
            items,
            global_discount=quantize_financial(global_discount),
            aplicar_recargo_equivalencia=aplicar_recargo_equivalencia,
        )

        desglose = [
            {
                "tipo_iva_porcentaje": float(decimal_to_db_numeric(d.tipo_iva_porcentaje)),
                "base_imponible": float(decimal_to_db_numeric(d.base_imponible)),
                "cuota_iva": float(decimal_to_db_numeric(d.cuota_iva)),
                "cuota_recargo_equivalencia": float(decimal_to_db_numeric(d.cuota_recargo_equivalencia)),
            }
            for d in tot.desglose_por_tipo
        ]
        lineas_out = [
            {
                "indice": x.indice,
                "cantidad": float(decimal_to_db_numeric(x.cantidad)),
                "precio_unitario": float(decimal_to_db_numeric(x.precio_unitario)),
                "base_imponible": float(decimal_to_db_numeric(x.base_imponible)),
                "tipo_iva_porcentaje": float(decimal_to_db_numeric(x.tipo_iva_porcentaje)),
                "descuento_linea": float(decimal_to_db_numeric(x.descuento_linea)),
            }
            for x in tot.lineas
        ]

        return FacturaRecalculateOut(
            factura_id=fid,
            base_imponible=float(decimal_to_db_numeric(tot.base_imponible_total)),
            cuota_iva=float(decimal_to_db_numeric(tot.cuota_iva_total)),
            cuota_recargo_equivalencia=float(decimal_to_db_numeric(tot.cuota_recargo_equivalencia_total)),
            total_factura=float(decimal_to_db_numeric(tot.total_factura)),
            desglose_por_tipo=desglose,
            lineas=lineas_out,
            ajuste_centimos=float(decimal_to_db_numeric(tot.ajuste_centimos)),
            importe_descuento_global_aplicado=float(decimal_to_db_numeric(tot.importe_descuento_global_aplicado)),
        )


def _factura_pdf_data_to_pdf_bytes(pdf: FacturaPdfDataOut) -> bytes:
    from app.services.pdf_service import generar_pdf_factura

    datos_empresa: dict[str, Any] = {
        "nombre": pdf.emisor.nombre,
        "nif": pdf.emisor.nif,
        "numero_factura": pdf.numero_factura,
        "fecha_emision": pdf.fecha_emision.isoformat(),
        "num_factura": pdf.num_factura_verifactu or pdf.numero_factura,
        "base_imponible": pdf.base_imponible,
        "cuota_iva": pdf.cuota_iva,
        "total_factura": pdf.total_factura,
        "iva_porcentaje": pdf.tipo_iva_porcentaje,
        "hash_registro": pdf.hash_registro or pdf.fingerprint_completo or "",
        "qr_verifactu_base64": pdf.verifactu_qr_base64,
    }
    datos_cliente: dict[str, Any] = {
        "nombre": pdf.receptor.nombre,
        "nif": pdf.receptor.nif or "",
        "id": "",
    }
    conceptos = [{"nombre": ln.concepto, "precio": ln.importe} for ln in pdf.lineas]
    return generar_pdf_factura(datos_empresa, datos_cliente, conceptos)
