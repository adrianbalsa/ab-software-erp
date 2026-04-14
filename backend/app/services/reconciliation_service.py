from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any
from uuid import UUID

import anyio
from rapidfuzz import fuzz

from app.db.supabase import SupabaseAsync
from app.schemas.conciliacion import ConciliacionSugerenciaLLM, ConciliarAiOut

_log = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _invoice_number(row: dict[str, Any]) -> str:
    return str(row.get("numero_factura") or row.get("num_factura") or "").strip()


def _two_dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except Exception:
        return Decimal("0.00")


def _tx_context_empresa(transaction: dict[str, Any]) -> str:
    """
    Devuelve el contexto de empresa propagado por conectores de banca.
    Prioriza ``dummy_empresa_id`` cuando existe (tests de estrés), y cae a ``empresa_id``.
    """
    dummy = str(transaction.get("dummy_empresa_id") or "").strip()
    if dummy:
        return dummy
    return str(transaction.get("empresa_id") or "").strip()


def _tx_reference_blob(transaction: dict[str, Any]) -> str:
    """
    Texto agregado para detectar referencias de factura en distintos formatos de bancos.
    """
    parts = [
        str(transaction.get("description") or ""),
        str(transaction.get("reference") or ""),
        str(transaction.get("concept") or ""),
        str(transaction.get("concepto") or ""),
        str(transaction.get("remittance_info") or ""),
        str(transaction.get("remittance_information") or ""),
        str(transaction.get("end_to_end_id") or ""),
        str(transaction.get("transaction_id") or ""),
    ]
    return " ".join(parts).casefold()


def match_unreconciled_to_invoices(
    *,
    bank_rows: list[dict[str, Any]],
    facturas_emitidas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Reglas:
    - Importe de movimiento **estrictamente positivo** y, en dos decimales, **igual** a ``total_factura``.
    - ``numero_factura`` (o ``num_factura``) debe aparecer en ``description`` (comparación case-insensitive).
    - Cada factura y cada movimiento se emparejan como máximo una vez (orden estable por ``id`` / ``transaction_id``).
    """
    invs = sorted(
        (
            f
            for f in facturas_emitidas
            if _two_dec(f.get("total_factura")) > 0 and _invoice_number(f)
        ),
        key=lambda x: int(x.get("id") or 0),
    )
    txs = sorted(
        (t for t in bank_rows if _two_dec(t.get("amount")) > 0),
        key=lambda t: str(t.get("transaction_id") or ""),
    )

    matched_inv: set[int] = set()
    matched_tx: set[str] = set()
    result: list[dict[str, Any]] = []

    for tx in txs:
        tx_id = str(tx.get("transaction_id") or "").strip()
        if not tx_id or tx_id in matched_tx:
            continue

        for inv in invs:
            fid = int(inv.get("id") or 0)
            if fid in matched_inv:
                continue
            if not match_invoice_transaction_pair(invoice=inv, transaction=tx):
                continue

            total = _two_dec(inv.get("total_factura"))
            amt = _two_dec(tx.get("amount"))
            matched_inv.add(fid)
            matched_tx.add(tx_id)
            bd = tx.get("booked_date")
            if hasattr(bd, "isoformat"):
                fecha_cobro = bd.isoformat()[:10]
            else:
                fecha_cobro = str(bd)[:10] if bd else date.today().isoformat()
            result.append(
                {
                    "factura_id": fid,
                    "transaction_id": tx_id,
                    "total_factura": float(total),
                    "importe_movimiento": float(amt),
                    "fecha_cobro_real": fecha_cobro,
                }
            )
            break

    return result


def match_invoice_transaction_pair(
    *,
    invoice: dict[str, Any],
    transaction: dict[str, Any],
) -> bool:
    """
    Regla base de conciliación para scaffold Open Banking/SEPA:
    - Importe factura == importe movimiento con cuantización a 2 decimales (ROUND_HALF_EVEN).
    - Referencia/concepto contiene el número de factura (case-insensitive).
    [cite: 2026-03-30]
    """
    total = _two_dec(invoice.get("total_factura"))
    amount = _two_dec(transaction.get("amount"))
    if total <= 0 or amount <= 0 or total != amount:
        return False

    inv_ctx = str(invoice.get("dummy_empresa_id") or invoice.get("empresa_id") or "").strip()
    tx_ctx = _tx_context_empresa(transaction)
    if inv_ctx and tx_ctx and inv_ctx != tx_ctx:
        return False

    numero = _invoice_number(invoice)
    if not numero:
        return False

    hay_numero = numero.casefold() in _tx_reference_blob(transaction)
    return hay_numero


class ReconciliationService:
    """Conciliación automática facturas ↔ bank_transactions."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def auto_reconcile_invoices(self, empresa_id: str) -> tuple[int, list[dict[str, Any]]]:
        """
        Cruza movimientos no conciliados (importe > 0) con facturas ``estado_cobro='emitida'``.
        Actualiza factura (cobrada, fecha_cobro_real, matched_transaction_id, pago_id) y marca el movimiento.
        """
        res_tx: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("empresa_id", empresa_id)
            .eq("reconciled", False)
        )
        tx_rows: list[dict[str, Any]] = (res_tx.data or []) if hasattr(res_tx, "data") else []

        res_f: Any = await self._db.execute(
            self._db.table("facturas")
            .select(
                "id, total_factura, numero_factura, num_factura, estado_cobro, empresa_id"
            )
            .eq("empresa_id", empresa_id)
            .eq("estado_cobro", "emitida")
        )
        fac_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []

        pairs = match_unreconciled_to_invoices(bank_rows=tx_rows, facturas_emitidas=fac_rows)
        detalle: list[dict[str, Any]] = []

        for p in pairs:
            fid = int(p["factura_id"])
            tx_id = str(p["transaction_id"])
            fecha = str(p["fecha_cobro_real"])[:10]

            await self._db.execute(
                self._db.table("facturas")
                .update(
                    {
                        "estado_cobro": "cobrada",
                        "pago_id": tx_id,
                        "matched_transaction_id": tx_id,
                        "fecha_cobro_real": fecha,
                    }
                )
                .eq("id", fid)
                .eq("empresa_id", empresa_id)
                .eq("estado_cobro", "emitida")
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                self._db.table("bank_transactions")
                .update({"reconciled": True, "updated_at": now_iso})
                .eq("empresa_id", empresa_id)
                .eq("transaction_id", tx_id)
            )

            detalle.append(
                {
                    "factura_id": fid,
                    "transaction_id": tx_id,
                    "total_factura": p["total_factura"],
                    "importe_movimiento": p["importe_movimiento"],
                    "fecha_cobro_real": fecha,
                }
            )

        if pairs:
            _log.info(
                "conciliación automática: empresa_id=%s coincidencias=%s",
                empresa_id,
                len(pairs),
            )

        return len(pairs), detalle

    async def auto_reconcile_all(self) -> tuple[int, dict[str, int]]:
        """
        Ejecuta conciliación automática para todas las empresas con facturas o movimientos bancarios.
        """
        empresas: set[str] = set()

        res_f: Any = await self._db.execute(self._db.table("facturas").select("empresa_id"))
        for row in (res_f.data or []) if hasattr(res_f, "data") else []:
            eid = str(row.get("empresa_id") or "").strip()
            if eid:
                empresas.add(eid)

        res_b: Any = await self._db.execute(self._db.table("bank_transactions").select("empresa_id"))
        for row in (res_b.data or []) if hasattr(res_b, "data") else []:
            eid = str(row.get("empresa_id") or "").strip()
            if eid:
                empresas.add(eid)

        total = 0
        per_empresa: dict[str, int] = {}
        for eid in sorted(empresas):
            n, _ = await self.auto_reconcile_invoices(eid)
            per_empresa[eid] = n
            total += n
        return total, per_empresa

    # ── Conciliación asistida por IA (movimientos_bancarios) ─────────────────

    async def _cargar_facturas_no_cobradas(self, *, empresa_id: str) -> list[dict[str, Any]]:
        res: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id, total_factura, numero_factura, num_factura, fecha_emision, estado_cobro, cliente")
            .eq("empresa_id", empresa_id)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[dict[str, Any]] = []
        for r in rows:
            st = str(r.get("estado_cobro") or "").strip().lower()
            if st == "cobrada" or st == "pagada":
                continue
            try:
                tf = float(r.get("total_factura") or 0.0)
            except (TypeError, ValueError):
                tf = 0.0
            if tf <= 0:
                continue
            out.append(dict(r))
        return out

    async def _enriquecer_nombres_cliente(
        self, *, empresa_id: str, facturas: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        ids: set[str] = set()
        for r in facturas:
            cid = r.get("cliente")
            if cid is not None:
                ids.add(str(cid).strip())
        if not ids:
            return [{**r, "cliente_nombre": None} for r in facturas]
        nombres: dict[str, str] = {}
        try:
            res: Any = await self._db.execute(
                self._db.table("clientes")
                .select("id, nombre, nombre_comercial")
                .eq("empresa_id", empresa_id)
                .in_("id", list(ids))
            )
            for row in (res.data or []) if hasattr(res, "data") else []:
                i = str(row.get("id") or "").strip()
                if not i:
                    continue
                nc = (row.get("nombre_comercial") or row.get("nombre") or "").strip()
                nombres[i] = nc or i
        except Exception:
            pass
        enriched: list[dict[str, Any]] = []
        for r in facturas:
            cid = str(r.get("cliente") or "").strip()
            enriched.append({**r, "cliente_nombre": nombres.get(cid)})
        return enriched

    async def _cargar_movimientos_pendientes_positivos(self, *, empresa_id: str) -> list[dict[str, Any]]:
        try:
            res: Any = await self._db.execute(
                self._db.table("movimientos_bancarios")
                .select("id, fecha, concepto, importe, iban_origen, estado")
                .eq("empresa_id", empresa_id)
                .eq("estado", "Pendiente")
            )
        except Exception as exc:
            _log.warning("movimientos_bancarios no disponible: %s", exc)
            return []
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                imp = float(r.get("importe") or 0.0)
            except (TypeError, ValueError):
                imp = 0.0
            if imp <= 0:
                continue
            out.append(dict(r))
        return out

    @staticmethod
    def _openai_configured() -> bool:
        return bool((os.getenv("OPENAI_API_KEY") or "").strip())

    @staticmethod
    def _llm_model() -> str:
        return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    def _llm_conciliacion_sync(
        self,
        *,
        facturas_json: str,
        movimientos_json: str,
    ) -> str:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada")

        system = (
            "Eres un contable experto en conciliación bancaria para transporte y logística. "
            "Debes emparejar cada movimiento bancario entrante (importe > 0) con como mucho una factura "
            "pendiente de cobro, o indicar que no hay emparejamiento razonable.\n"
            "Criterios: importe exacto o muy cercano (tolerancia máxima 0,05 EUR salvo error redondeo), "
            "nombre del cliente o número de factura reconocible en el concepto, fechas coherentes "
            "(cobro posterior o cercano a emisión).\n"
            "Responde SOLO con un JSON válido UTF-8 sin markdown, con esta forma exacta:\n"
            '{"sugerencias":[{"movimiento_id":"<UUID del movimiento>","factura_id":<entero id factura>,'
            '"confidence_score":0.0,"razonamiento":"texto breve en español"}]}\n'
            "Si no hay ningún emparejamiento fiable, devuelve {\"sugerencias\":[]}.\n"
            "Los movimiento_id y factura_id DEBEN copiarse exactamente de los listados proporcionados; "
            "no inventes identificadores."
        )
        user = (
            "FACTURAS_PENDIENTES_DE_COBRO (JSON):\n"
            f"{facturas_json}\n\n"
            "MOVIMIENTOS_BANCARIOS_PENDIENTES (JSON):\n"
            f"{movimientos_json}"
        )

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=self._llm_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        choice = resp.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            raise RuntimeError("LLM devolvió respuesta vacía")
        return content

    def _parsear_y_validar_sugerencias_llm(
        self,
        raw: str,
        *,
        movimientos: list[dict[str, Any]],
        facturas: list[dict[str, Any]],
    ) -> list[ConciliacionSugerenciaLLM]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido del LLM: {e}") from e

        arr = data.get("sugerencias")
        if arr is None:
            raise ValueError("Falta clave 'sugerencias' en JSON del LLM")
        if not isinstance(arr, list):
            raise ValueError("'sugerencias' debe ser un array")

        mov_by_id: dict[str, dict[str, Any]] = {}
        for m in movimientos:
            mid = str(m.get("id") or "").strip()
            if mid:
                mov_by_id[mid] = m
        fac_by_id: dict[int, dict[str, Any]] = {}
        for f in facturas:
            try:
                fid = int(f.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if fid > 0:
                fac_by_id[fid] = f

        out: list[ConciliacionSugerenciaLLM] = []
        seen_mov: set[str] = set()
        seen_fac: set[int] = set()

        for i, item in enumerate(arr):
            if not isinstance(item, dict):
                raise ValueError(f"Elemento {i} no es un objeto")
            mid_raw = str(item.get("movimiento_id") or "").strip()
            if not _UUID_RE.match(mid_raw):
                raise ValueError(f"movimiento_id inválido: {mid_raw!r}")
            if mid_raw not in mov_by_id:
                raise ValueError(f"movimiento_id no existe en el lote: {mid_raw}")
            if mid_raw in seen_mov:
                raise ValueError(f"movimiento duplicado en sugerencias: {mid_raw}")
            seen_mov.add(mid_raw)

            try:
                fid = int(item.get("factura_id"))
            except (TypeError, ValueError) as e:
                raise ValueError(f"factura_id inválido: {item.get('factura_id')!r}") from e
            if fid not in fac_by_id:
                raise ValueError(f"factura_id no existe en el lote: {fid}")
            if fid in seen_fac:
                raise ValueError(f"factura duplicada en sugerencias: {fid}")
            seen_fac.add(fid)

            try:
                conf = float(item.get("confidence_score"))
            except (TypeError, ValueError) as e:
                raise ValueError("confidence_score inválido") from e
            razon = str(item.get("razonamiento") or "").strip()
            if not razon:
                raise ValueError("razonamiento vacío")

            out.append(
                ConciliacionSugerenciaLLM(
                    movimiento_id=UUID(mid_raw),
                    factura_id=fid,
                    confidence_score=min(1.0, max(0.0, conf)),
                    razonamiento=razon[:4000],
                )
            )

        return out

    async def generar_sugerencias_conciliacion(self, *, empresa_id: str) -> list[ConciliacionSugerenciaLLM]:
        """
        Llama al LLM y valida contra los datos cargados. **No escribe en base de datos.**
        Lanza ``ValueError`` o ``RuntimeError`` si el JSON es inválido o los IDs no cuadran.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            raise ValueError("empresa_id requerido")

        facturas = await self._cargar_facturas_no_cobradas(empresa_id=eid)
        movimientos = await self._cargar_movimientos_pendientes_positivos(empresa_id=eid)
        facturas = await self._enriquecer_nombres_cliente(empresa_id=eid, facturas=facturas)

        if not movimientos or not facturas:
            return []

        if not self._openai_configured():
            raise RuntimeError("OPENAI_API_KEY no configurada para conciliación IA")

        fac_payload: list[dict[str, Any]] = []
        for f in facturas:
            fe = f.get("fecha_emision")
            fe_s = fe.isoformat()[:10] if hasattr(fe, "isoformat") else str(fe)[:10]
            fac_payload.append(
                {
                    "id": int(f.get("id") or 0),
                    "total_factura": float(f.get("total_factura") or 0.0),
                    "numero_factura": str(f.get("numero_factura") or f.get("num_factura") or ""),
                    "fecha_emision": fe_s,
                    "estado_cobro": str(f.get("estado_cobro") or ""),
                    "cliente_nombre": f.get("cliente_nombre"),
                }
            )

        mov_payload: list[dict[str, Any]] = []
        for m in movimientos:
            fd = m.get("fecha")
            fd_s = fd.isoformat()[:10] if hasattr(fd, "isoformat") else str(fd)[:10]
            mov_payload.append(
                {
                    "id": str(m.get("id") or ""),
                    "fecha": fd_s,
                    "concepto": str(m.get("concepto") or "")[:2000],
                    "importe": float(m.get("importe") or 0.0),
                    "iban_origen": m.get("iban_origen"),
                }
            )

        fac_json = json.dumps(fac_payload, ensure_ascii=False)
        mov_json = json.dumps(mov_payload, ensure_ascii=False)

        raw = await anyio.to_thread.run_sync(
            self._llm_conciliacion_sync,
            facturas_json=fac_json,
            movimientos_json=mov_json,
        )
        return self._parsear_y_validar_sugerencias_llm(
            raw,
            movimientos=movimientos,
            facturas=facturas,
        )

    async def persistir_sugerencias_ia(
        self,
        *,
        empresa_id: str,
        sugerencias: list[ConciliacionSugerenciaLLM],
    ) -> list[dict[str, Any]]:
        """Actualiza movimientos a estado Sugerido y vincula factura_id (metadatos IA)."""
        eid = str(empresa_id or "").strip()
        now_iso = datetime.now(timezone.utc).isoformat()
        detalle: list[dict[str, Any]] = []
        for s in sugerencias:
            payload = {
                "estado": "Sugerido",
                "factura_id": s.factura_id,
                "confidence_score": float(s.confidence_score),
                "razonamiento_ia": s.razonamiento,
                "updated_at": now_iso,
            }
            await self._db.execute(
                self._db.table("movimientos_bancarios")
                .update(payload)
                .eq("id", str(s.movimiento_id))
                .eq("empresa_id", eid)
                .eq("estado", "Pendiente")
            )
            detalle.append(
                {
                    "movimiento_id": str(s.movimiento_id),
                    "factura_id": s.factura_id,
                    "confidence_score": s.confidence_score,
                    "razonamiento": s.razonamiento,
                }
            )
        return detalle

    async def ejecutar_conciliacion_ia_completa(self, *, empresa_id: str) -> ConciliarAiOut:
        """
        Genera sugerencias con LLM y persiste. Si el LLM o la validación fallan, **no modifica la BD**.
        """
        try:
            sugerencias = await self.generar_sugerencias_conciliacion(empresa_id=empresa_id)
        except (ValueError, RuntimeError):
            _log.exception("conciliación IA: fallo en generación/validación (sin cambios en BD)")
            raise

        if not sugerencias:
            return ConciliarAiOut(sugerencias_guardadas=0, detalle=[])

        try:
            detalle = await self.persistir_sugerencias_ia(empresa_id=empresa_id, sugerencias=sugerencias)
        except Exception:
            _log.exception("conciliación IA: fallo al persistir")
            raise RuntimeError("No se pudieron guardar las sugerencias en base de datos.") from None

        return ConciliarAiOut(sugerencias_guardadas=len(detalle), detalle=detalle)

    async def listar_movimientos_sugeridos(self, *, empresa_id: str) -> list[dict[str, Any]]:
        eid = str(empresa_id or "").strip()
        res: Any = await self._db.execute(
            self._db.table("movimientos_bancarios")
            .select("*")
            .eq("empresa_id", eid)
            .eq("estado", "Sugerido")
            .order("fecha", desc=True)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[dict[str, Any]] = []
        for r in rows:
            fid = r.get("factura_id")
            extra: dict[str, Any] = {
                "factura_numero": None,
                "factura_total": None,
                "factura_fecha": None,
                "cliente_nombre": None,
            }
            if fid is not None:
                try:
                    rf: Any = await self._db.execute(
                        self._db.table("facturas")
                        .select("numero_factura, num_factura, total_factura, fecha_emision, cliente")
                        .eq("empresa_id", eid)
                        .eq("id", int(fid))
                        .limit(1)
                    )
                    fr = (rf.data or []) if hasattr(rf, "data") else []
                    if fr:
                        frow = fr[0]
                        extra["factura_numero"] = str(
                            frow.get("numero_factura") or frow.get("num_factura") or ""
                        )
                        extra["factura_total"] = float(frow.get("total_factura") or 0.0)
                        fe = frow.get("fecha_emision")
                        extra["factura_fecha"] = (
                            fe.isoformat()[:10] if hasattr(fe, "isoformat") else str(fe)[:10]
                        )
                        cid = frow.get("cliente")
                        if cid:
                            try:
                                rc: Any = await self._db.execute(
                                    self._db.table("clientes")
                                    .select("nombre, nombre_comercial")
                                    .eq("empresa_id", eid)
                                    .eq("id", str(cid))
                                    .limit(1)
                                )
                                cr = (rc.data or []) if hasattr(rc, "data") else []
                                if cr:
                                    extra["cliente_nombre"] = str(
                                        cr[0].get("nombre_comercial") or cr[0].get("nombre") or ""
                                    ).strip()
                            except Exception:
                                pass
                except Exception:
                    pass
            fd = r.get("fecha")
            out.append(
                {
                    "movimiento_id": str(r.get("id") or ""),
                    "fecha": fd.isoformat()[:10] if hasattr(fd, "isoformat") else str(fd)[:10],
                    "concepto": str(r.get("concepto") or ""),
                    "importe": float(r.get("importe") or 0.0),
                    "iban_origen": r.get("iban_origen"),
                    "factura_id": int(fid) if fid is not None else None,
                    "confidence_score": float(r.get("confidence_score") or 0.0)
                    if r.get("confidence_score") is not None
                    else None,
                    "razonamiento_ia": r.get("razonamiento_ia"),
                    **extra,
                }
            )
        return out

    async def confirmar_sugerencia(
        self,
        *,
        empresa_id: str,
        movimiento_id: UUID,
        aprobar: bool,
    ) -> None:
        eid = str(empresa_id or "").strip()
        res: Any = await self._db.execute(
            self._db.table("movimientos_bancarios")
            .select("id, factura_id, fecha, estado")
            .eq("empresa_id", eid)
            .eq("id", str(movimiento_id))
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Movimiento no encontrado")
        row = rows[0]
        if str(row.get("estado") or "") != "Sugerido":
            raise ValueError("El movimiento no está en estado Sugerido")
        fid_raw = row.get("factura_id")
        if fid_raw is None:
            raise ValueError("Movimiento sin factura vinculada")
        fid = int(fid_raw)
        fecha_mov = row.get("fecha")
        fecha_cobro = (
            fecha_mov.isoformat()[:10]
            if hasattr(fecha_mov, "isoformat")
            else str(fecha_mov)[:10]
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        if not aprobar:
            await self._db.execute(
                self._db.table("movimientos_bancarios")
                .update(
                    {
                        "estado": "Pendiente",
                        "factura_id": None,
                        "confidence_score": None,
                        "razonamiento_ia": None,
                        "updated_at": now_iso,
                    }
                )
                .eq("id", str(movimiento_id))
                .eq("empresa_id", eid)
            )
            return

        fac_chk: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id, estado_cobro")
            .eq("id", fid)
            .eq("empresa_id", eid)
            .limit(1)
        )
        fac_rows: list[dict[str, Any]] = (fac_chk.data or []) if hasattr(fac_chk, "data") else []
        if not fac_rows:
            raise ValueError("Factura no encontrada para esta empresa")
        if str(fac_rows[0].get("estado_cobro") or "") == "cobrada":
            raise ValueError("La factura ya está marcada como cobrada")

        await self._db.execute(
            self._db.table("facturas")
            .update(
                {
                    "estado_cobro": "cobrada",
                    "fecha_cobro_real": fecha_cobro,
                    "pago_id": f"movimiento_bancario:{movimiento_id}",
                }
            )
            .eq("id", fid)
            .eq("empresa_id", eid)
            .neq("estado_cobro", "cobrada")
        )

        await self._db.execute(
            self._db.table("movimientos_bancarios")
            .update({"estado": "Conciliado", "updated_at": now_iso})
            .eq("id", str(movimiento_id))
            .eq("empresa_id", eid)
            .eq("estado", "Sugerido")
        )


class ReconciliationEngine:
    """
    Motor de conciliación para cola `webhook_events` (GoCardless).

    Flujo:
    - Lee eventos `PENDING`.
    - Extrae importe, descripción y referencia/mandato.
    - Busca facturas no cobradas en margen ±5%.
    - Fuzzy match descripción bancaria vs nombre cliente (`rapidfuzz`).
    - Si score > 0.95, marca factura cobrada y evento COMPLETED.
    - Si no, evento FAILED + `error_log`.
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _extract_payload_event(payload: Any) -> dict[str, Any]:
        obj: Any = payload
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except Exception:
                return {}
        if not isinstance(obj, dict):
            return {}
        if isinstance(obj.get("events"), list):
            events = obj.get("events") or []
            if events and isinstance(events[0], dict):
                return dict(events[0])
        if isinstance(obj.get("event"), dict):
            return dict(obj["event"])
        return dict(obj)

    @staticmethod
    def _extract_amount_desc_ref(event: dict[str, Any]) -> tuple[Decimal | None, str, str, str]:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        links = event.get("links") if isinstance(event.get("links"), dict) else {}
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}

        amount_minor = (
            details.get("amount")
            or details.get("amount_minor")
            or event.get("amount_minor")
            or event.get("amount_in_minor")
        )
        amount_major = event.get("amount") or details.get("amount_major")
        amount_raw = amount_minor if amount_minor is not None else amount_major
        amount = ReconciliationEngine._to_decimal(amount_raw)
        if amount is not None and amount_minor is not None:
            amount = (amount / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_EVEN
            )
        if amount is not None and amount_major is not None and amount_minor is None:
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

        description = str(
            details.get("description")
            or details.get("cause")
            or event.get("description")
            or metadata.get("description")
            or ""
        ).strip()
        reference = str(
            metadata.get("reference")
            or links.get("mandate")
            or links.get("payment")
            or event.get("resource_id")
            or ""
        ).strip()
        empresa_ctx = str(
            metadata.get("empresa_id")
            or metadata.get("dummy_empresa_id")
            or event.get("empresa_id")
            or ""
        ).strip()
        return amount, description, reference, empresa_ctx

    async def _clientes_nombre_por_id(self, *, empresa_id: str, cliente_ids: set[str]) -> dict[str, str]:
        if not cliente_ids:
            return {}
        try:
            res: Any = await self._db.execute(
                self._db.table("clientes")
                .select("id,nombre,nombre_comercial")
                .eq("empresa_id", empresa_id)
                .in_("id", list(cliente_ids))
            )
            out: dict[str, str] = {}
            for row in (res.data or []) if hasattr(res, "data") else []:
                cid = str(row.get("id") or "").strip()
                if not cid:
                    continue
                out[cid] = str(
                    row.get("nombre_comercial") or row.get("nombre") or ""
                ).strip()
            return out
        except Exception:
            return {}

    async def _candidate_invoices(
        self,
        *,
        amount: Decimal,
        empresa_ctx: str | None,
    ) -> list[dict[str, Any]]:
        res: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id,empresa_id,total_factura,estado_cobro,fecha_emision,cliente,numero_factura,num_factura")
            .order("fecha_emision", desc=True)
            .limit(500)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        low = (amount * Decimal("0.95")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        high = (amount * Decimal("1.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        out: list[dict[str, Any]] = []
        for r in rows:
            st = str(r.get("estado_cobro") or "").strip().lower()
            if st == "cobrada":
                continue
            rid = str(r.get("empresa_id") or "").strip()
            if empresa_ctx and rid and rid != empresa_ctx:
                continue
            tot = self._to_decimal(r.get("total_factura"))
            if tot is None:
                continue
            tot_q = tot.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            if low <= tot_q <= high:
                out.append(dict(r))
        return out

    async def _pick_best_match(
        self,
        *,
        amount: Decimal,
        description: str,
        reference: str,
        empresa_ctx: str | None,
    ) -> tuple[dict[str, Any] | None, float]:
        candidates = await self._candidate_invoices(amount=amount, empresa_ctx=empresa_ctx)
        if not candidates:
            return None, 0.0

        # Agrupar por empresa para enriquecer nombres de cliente.
        by_empresa: dict[str, list[dict[str, Any]]] = {}
        for c in candidates:
            by_empresa.setdefault(str(c.get("empresa_id") or "").strip(), []).append(c)

        best: dict[str, Any] | None = None
        best_score = 0.0
        desc_norm = description.strip()
        ref_norm = reference.strip().casefold()

        for eid, bucket in by_empresa.items():
            ids = {str(x.get("cliente") or "").strip() for x in bucket if x.get("cliente") is not None}
            name_map = await self._clientes_nombre_por_id(empresa_id=eid, cliente_ids=ids)
            for inv in bucket:
                cid = str(inv.get("cliente") or "").strip()
                cname = name_map.get(cid, "")
                fuzzy = (
                    float(fuzz.token_set_ratio(desc_norm, cname)) / 100.0
                    if desc_norm and cname
                    else 0.0
                )
                inv_no = str(
                    inv.get("numero_factura") or inv.get("num_factura") or ""
                ).strip().casefold()
                ref_hit = 1.0 if inv_no and inv_no in ref_norm else 0.0
                score = max(fuzzy, ref_hit)
                if score > best_score:
                    best_score = score
                    best = inv
        return best, best_score

    async def _mark_event(
        self,
        *,
        event_id: int,
        status: str,
        error_log: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"status": status}
        if error_log is not None:
            payload["error_log"] = error_log[:2000]
        await self._db.execute(
            self._db.table("webhook_events")
            .update(payload)
            .eq("id", event_id)
        )

    async def _mark_invoice_paid(
        self,
        *,
        invoice: dict[str, Any],
        reference: str,
    ) -> None:
        fid = int(invoice.get("id"))
        eid = str(invoice.get("empresa_id") or "").strip()
        if not eid:
            raise ValueError("invoice empresa_id missing")

        now_iso = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            self._db.table("facturas")
            .update(
                {
                    "estado_cobro": "cobrada",
                    "payment_status": "PAID",
                    "pago_id": reference or f"gocardless:auto:{fid}",
                    "fecha_cobro_real": now_iso[:10],
                }
            )
            .eq("id", fid)
            .eq("empresa_id", eid)
            .neq("estado_cobro", "cobrada")
        )

        fe = str(invoice.get("fecha_emision") or "").strip()
        month = fe[:7] if len(fe) >= 7 else ""
        if month:
            await self._db.rpc(
                "_upsert_monthly_kpis",
                {"p_empresa_id": eid, "p_period_month": month},
            )

    async def process_pending_event(self, event_row: dict[str, Any]) -> bool:
        event_id = int(event_row.get("id") or 0)
        if event_id <= 0:
            return False
        payload_event = self._extract_payload_event(event_row.get("payload"))
        amount, description, reference, empresa_ctx = self._extract_amount_desc_ref(payload_event)
        if amount is None or amount <= 0:
            await self._mark_event(
                event_id=event_id,
                status="FAILED",
                error_log="No matching invoice found: invalid or missing amount",
            )
            return False

        best, score = await self._pick_best_match(
            amount=amount,
            description=description,
            reference=reference,
            empresa_ctx=empresa_ctx or None,
        )
        if best is None or score <= 0.95:
            await self._mark_event(
                event_id=event_id,
                status="FAILED",
                error_log="No matching invoice found",
            )
            return False

        await self._mark_invoice_paid(invoice=best, reference=reference)
        await self._mark_event(event_id=event_id, status="COMPLETED", error_log=None)
        return True

    async def poll_pending_queue(self, *, limit: int = 50) -> dict[str, int]:
        lim = max(1, min(500, int(limit)))
        res: Any = await self._db.execute(
            self._db.table("webhook_events")
            .select("id,provider,event_type,payload,status,created_at")
            .eq("provider", "gocardless")
            .eq("status", "PENDING")
            .order("created_at", desc=False)
            .limit(lim)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []

        completed = 0
        failed = 0
        for row in rows:
            try:
                ok = await self.process_pending_event(dict(row))
                if ok:
                    completed += 1
                else:
                    failed += 1
            except Exception as exc:
                rid = int(row.get("id") or 0)
                if rid > 0:
                    await self._mark_event(
                        event_id=rid,
                        status="FAILED",
                        error_log=f"No matching invoice found: {str(exc)}",
                    )
                failed += 1
        return {"processed": len(rows), "completed": completed, "failed": failed}
