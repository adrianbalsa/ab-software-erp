from __future__ import annotations

import time
from typing import Any

from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db.supabase import SupabaseAsync
from app.schemas.gasto import GastoCreate, GastoOCRHint, GastoOut
from app.services.ocr_service import OCRService
from app.core.crypto import pii_crypto


class GastosService:
    """
    Migrado desde `views/gastos_view.py`.

    - Persiste gastos en `gastos` con `empresa_id` siempre inyectado por la capa API (JWT).
    - Subida de evidencia al bucket `tickets-gastos`.
    - OCR: Azure Document Intelligence (`prebuilt-invoice`) vía `OCRService`.
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    @staticmethod
    def _require_empresa_id(empresa_id: str) -> str:
        """Ninguna escritura sin empresa válida (JWT → profiles)."""
        e = str(empresa_id or "").strip()
        if not e:
            raise ValueError("empresa_id inválido: operación denegada")
        return e

    async def list_gastos(self, *, empresa_id: str) -> list[GastoOut]:
        eid = self._require_empresa_id(empresa_id)
        q = filter_not_deleted(
            self._db.table("gastos")
            .select("*")
            .eq("empresa_id", eid)
            .order("fecha", desc=True)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[GastoOut] = []
        for row in rows:
            try:
                rn = dict(row)
                raw_nif = rn.get("nif_proveedor")
                if isinstance(raw_nif, str) and raw_nif.strip():
                    rn["nif_proveedor"] = pii_crypto.decrypt_pii(raw_nif) or raw_nif
                out.append(GastoOut(**rn))
            except Exception:
                continue
        return out

    @staticmethod
    def _total_eur_for_compliance(gasto_in: GastoCreate) -> float | None:
        """Total en EUR para trazabilidad fiscal (VeriFactu)."""
        if gasto_in.total_eur is not None:
            return float(gasto_in.total_eur)
        if str(gasto_in.moneda).upper() == "EUR":
            return float(gasto_in.total_chf)
        return None

    async def create_gasto(
        self,
        *,
        empresa_id: str,
        empleado: str,
        gasto_in: GastoCreate,
        evidencia_bytes: bytes | None = None,
        evidencia_filename: str | None = None,
        evidencia_content_type: str | None = None,
    ) -> GastoOut:
        eid = self._require_empresa_id(empresa_id)
        evidencia_url = gasto_in.evidencia_url

        if evidencia_bytes is not None and evidencia_filename:
            path = f"{eid}/{int(time.time())}_{evidencia_filename}"
            await self._db.storage_upload(
                bucket="tickets-gastos",
                path=path,
                content=evidencia_bytes,
                content_type=evidencia_content_type,
            )
            evidencia_url = path

        total_eur = self._total_eur_for_compliance(gasto_in)

        payload: dict[str, Any] = {
            "empresa_id": eid,
            "empleado": empleado,
            "proveedor": gasto_in.proveedor,
            "fecha": gasto_in.fecha.isoformat(),
            "total_chf": float(gasto_in.total_chf),
            "categoria": gasto_in.categoria,
            "concepto": gasto_in.concepto,
            "moneda": gasto_in.moneda,
            "evidencia_url": evidencia_url,
        }
        if gasto_in.porte_id is not None:
            payload["porte_id"] = str(gasto_in.porte_id)
        if gasto_in.nif_proveedor is not None:
            payload["nif_proveedor"] = gasto_in.nif_proveedor
        if gasto_in.iva is not None:
            payload["iva"] = float(gasto_in.iva)
        if total_eur is not None:
            payload["total_eur"] = float(total_eur)

        try:
            res: Any = await self._db.execute(self._db.table("gastos").insert(payload))
        except Exception as exc:
            # Compatibilidad con entornos donde la migración `gastos.porte_id` aún no se aplicó.
            if "porte_id" in payload and "porte_id" in str(exc).lower():
                payload.pop("porte_id", None)
                res = await self._db.execute(self._db.table("gastos").insert(payload))
            else:
                raise
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise RuntimeError("Supabase insert gasto returned no rows")
        rn = dict(rows[0])
        raw_nif = rn.get("nif_proveedor")
        if isinstance(raw_nif, str) and raw_nif.strip():
            rn["nif_proveedor"] = pii_crypto.decrypt_pii(raw_nif) or raw_nif
        return GastoOut(**rn)

    async def soft_delete_gasto(self, *, empresa_id: str, gasto_id: str) -> None:
        eid = self._require_empresa_id(empresa_id)
        gid = str(gasto_id or "").strip()
        if not gid:
            raise ValueError("gasto_id inválido")
        await self._db.execute(
            self._db.table("gastos")
            .update(soft_delete_payload())
            .eq("empresa_id", eid)
            .eq("id", gid)
            .is_("deleted_at", "null")
        )

    @staticmethod
    def _dict_to_gasto_ocr_hint(data: dict[str, Any]) -> GastoOCRHint:
        """
        Mapea la salida de `OCRService.analizar_ticket` al esquema API.

        Azure prebuilt-invoice → GastoOCRHint:
        - VendorName → proveedor
        - VendorTaxId → nif_proveedor
        - TotalTax → iva
        - InvoiceTotal (+ currency) → total, moneda
        """
        if not data:
            return GastoOCRHint()

        def _empty_to_none(s: str | None) -> str | None:
            t = (s or "").strip()
            return t or None

        total = data.get("total")
        iva = data.get("iva")

        oc = data.get("ocr_confidence")
        conf_f = float(oc) if oc is not None else None
        return GastoOCRHint(
            proveedor=_empty_to_none(data.get("proveedor")),
            fecha=data.get("fecha") or None,
            total=float(total) if total is not None else None,
            moneda=_empty_to_none(data.get("moneda")),
            concepto=_empty_to_none(data.get("concepto")),
            nif_proveedor=_empty_to_none(data.get("nif_proveedor")),
            iva=float(iva) if iva is not None else None,
            ocr_confidence=conf_f,
            requires_manual_review=bool(data.get("requires_manual_review")),
        )

    async def ocr_extract_hint(self, *, content: bytes, filename: str) -> GastoOCRHint:
        """
        Analiza el ticket/factura con Azure `prebuilt-invoice` y devuelve `GastoOCRHint`.
        """
        _ = filename
        ocr = OCRService()
        raw = await ocr.analizar_ticket(content)
        return self._dict_to_gasto_ocr_hint(raw)
