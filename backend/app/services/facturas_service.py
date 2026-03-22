from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from app.core.plans import PLAN_ENTERPRISE, fetch_empresa_plan, normalize_plan
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.integrations.pdf_adapter import generar_pdf_factura_base64
from app.schemas.cliente import ClienteOut
from app.schemas.factura import FacturaCreateFromPortes, FacturaGenerateResult, FacturaOut
from app.services.aeat_qr_service import generar_qr_verifactu
from app.services.aeat_xml_service import generar_xml_alta_factura
from app.services.auditoria_service import AuditoriaService
from app.services.eco_service import co2_emitido_desde_porte_row
from app.services.verifactu_service import VerifactuService


def _negate_invoice_amount(value: Any) -> float:
    v = float(value or 0.0)
    if v == 0.0:
        return 0.0
    return -abs(v)


def _clone_snapshot_con_importes_negativos(snapshot: Any) -> list[dict[str, Any]]:
    if not isinstance(snapshot, list):
        return []
    out: list[dict[str, Any]] = []
    for item in snapshot:
        if not isinstance(item, dict):
            continue
        line = dict(item)
        line["precio_pactado"] = _negate_invoice_amount(line.get("precio_pactado"))
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


class FacturasService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db
        self._audit = AuditoriaService(db)
        self._verifactu = VerifactuService(db)

    async def list_facturas(self, *, empresa_id: str | UUID) -> list[FacturaOut]:
        eid = _as_empresa_id_str(empresa_id)
        q = (
            self._db.table("facturas")
            .select("*")
            .eq("empresa_id", eid)
            .order("fecha_emision", desc=True)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[FacturaOut] = []
        for row in rows:
            try:
                out.append(FacturaOut(**row))
            except Exception:
                continue
        return out

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
                        nif_por_cliente[cid] = str(crow.get("nif") or "").strip()
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
    ) -> FacturaGenerateResult:
        """
        Genera factura desde portes pendientes con encadenamiento VeriFactu (SIF).

        1. **Encadenamiento**: ``obtener_ultimo_hash_y_secuencial(empresa_id)`` → ``hash_anterior``,
           ``siguiente_secuencial``.
        2. **Identidad**: ``nif_emisor`` desde ``empresas.nif``; NIF cliente desde ``clientes``.
        3. **Huella**: ``SHA256(NIF_Emisor + NIF_Cliente + Num_Factura + Fecha + Total + Hash_Anterior)``
           vía ``VerifactuService.generar_hash_factura`` → ``hash_registro``.
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

        # Valores congelados en factura (motor matemático / fiscal): independientes del porte tras emitir
        porte_lineas_snapshot: list[dict[str, Any]] = []
        total_km_estimados_snapshot = 0.0
        for r in portes_rows:
            km = float(r.get("km_estimados") or 0.0)
            precio = float(r.get("precio_pactado") or 0.0)
            total_km_estimados_snapshot += km
            porte_lineas_snapshot.append(
                {
                    "porte_id": str(r.get("id") or ""),
                    "precio_pactado": precio,
                    "km_estimados": km,
                    "fecha": str(r.get("fecha") or ""),
                    "origen": str(r.get("origen") or ""),
                    "destino": str(r.get("destino") or ""),
                    "descripcion": r.get("descripcion"),
                    "bultos": r.get("bultos"),
                }
            )

        base_imponible = float(sum(float(r.get("precio_pactado") or 0.0) for r in portes_rows))
        cuota_iva = base_imponible * (payload.iva_porcentaje / 100.0)
        total_factura = base_imponible + cuota_iva
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
                nif_emisor = str(empresa_row.get("nif") or "").strip()
        except Exception:
            pass
        try:
            res_nif_cli: Any = await self._db.execute(
                self._db.table("clientes").select("nif,nombre").eq("id", cid).limit(1)
            )
            crows: list[dict[str, Any]] = (res_nif_cli.data or []) if hasattr(res_nif_cli, "data") else []
            if crows:
                cliente_row = dict(crows[0])
                nif_cliente = str(cliente_row.get("nif") or "").strip()
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

        # --- 4) Huella digital: SHA256(NIF_Emisor + NIF_Cliente + Num_Factura + Fecha + Total + Hash_Anterior)
        try:
            hash_registro = self._verifactu.generar_hash_factura(
                nif_empresa=nif_emisor,
                nif_cliente=nif_cliente,
                num_factura=num_fact,
                fecha=str(fecha_iso),
                total=float(total_factura),
                hash_anterior=eslabon.hash_anterior,
            )
        except Exception as e:
            raise ValueError(
                f"Encadenamiento criptográfico VeriFactu: no se pudo generar el hash de registro: {e}"
            ) from e

        # Campos alineados con VeriFactu / SIF (tipo F1, huella y encadenamiento)
        factura_payload: dict[str, Any] = {
            "empresa_id": eid,
            "cliente": cid,
            "tipo_factura": "F1",
            "num_factura": num_fact,
            "numero_factura": num_fact,
            "nif_emisor": nif_emisor,
            "total_factura": total_factura,
            "base_imponible": base_imponible,
            "cuota_iva": cuota_iva,
            "fecha_emision": fecha_iso,
            "numero_secuencial": eslabon.siguiente_secuencial,
            "hash_anterior": eslabon.hash_anterior,
            "hash_registro": hash_registro,
            "hash_factura": hash_registro,
            "bloqueado": True,
            "porte_lineas_snapshot": porte_lineas_snapshot,
            "total_km_estimados_snapshot": total_km_estimados_snapshot,
            "estado_cobro": "emitida",
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

        cli_det: ClienteOut | None = None
        try:
            rcli: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("clientes").select("*").eq("empresa_id", eid).eq("id", cid).limit(1)
                )
            )
            crd: list[dict[str, Any]] = (rcli.data or []) if hasattr(rcli, "data") else []
            if crd:
                cli_det = ClienteOut(**crd[0])
        except Exception:
            cli_det = None

        factura_out = FacturaOut.model_validate({**factura_row, "cliente_detalle": cli_det})

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

            conceptos: list[dict[str, Any]] = []
            for line in porte_lineas_snapshot:
                nombre = f"{line.get('fecha', '')} {line.get('origen', '')} → {line.get('destino', '')}"
                if line.get("descripcion"):
                    nombre += f" | {line.get('descripcion')}"
                conceptos.append(
                    {"nombre": nombre[:120], "precio": float(line.get("precio_pactado") or 0.0)}
                )

            qr_vf_b64 = generar_qr_verifactu(
                nif_emisor=str(emp.get("nif") or nif_emisor or "").strip(),
                num_factura=str(factura_row.get("numero_factura") or factura_row.get("num_factura") or num_fact),
                fecha=str(factura_row.get("fecha_emision") or fecha_iso),
                importe_total=float(factura_row.get("total_factura") or total_factura),
            )
            datos_empresa = {
                "nombre": str(emp.get("nombre_comercial") or "AB Logistics"),
                "nif": str(emp.get("nif") or ""),
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
                "nif": str(cli.get("nif") or "").strip() or None,
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

        base_r = _negate_invoice_amount(orig.get("base_imponible"))
        cuota_r = _negate_invoice_amount(orig.get("cuota_iva"))
        total_orig = float(orig.get("total_factura") or 0.0)
        if total_orig == 0.0 and (base_r != 0.0 or cuota_r != 0.0):
            total_r = base_r + cuota_r
        else:
            total_r = _negate_invoice_amount(total_orig)

        nif_emisor = str(orig.get("nif_emisor") or "").strip()
        if not nif_emisor:
            try:
                res_ne: Any = await self._db.execute(
                    self._db.table("empresas").select("nif").eq("id", eid).limit(1)
                )
                ner: list[dict[str, Any]] = (res_ne.data or []) if hasattr(res_ne, "data") else []
                if ner:
                    nif_emisor = str(ner[0].get("nif") or "").strip()
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
                    nif_cliente = str(ncr[0].get("nif") or "").strip()
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

        hash_registro = self._verifactu.generar_hash_factura(
            nif_empresa=nif_emisor,
            nif_cliente=nif_cliente,
            num_factura=num_fact_r,
            fecha=str(fecha_iso),
            total=float(total_r),
            hash_anterior=hash_original,
            tipo_factura="R1",
            num_factura_rectificada=num_orig,
        )

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
            "nif_emisor": nif_emisor,
            "total_factura": total_r,
            "base_imponible": base_r,
            "cuota_iva": cuota_r,
            "fecha_emision": fecha_iso,
            "numero_secuencial": siguiente_seq,
            "hash_anterior": hash_original,
            "hash_registro": hash_registro,
            "hash_factura": hash_registro,
            "bloqueado": True,
            "porte_lineas_snapshot": porte_snap,
            "total_km_estimados_snapshot": km_val,
            "factura_rectificada_id": fid,
            "motivo_rectificacion": str(motivo).strip(),
            "estado_cobro": "emitida",
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

        return FacturaOut(**row_new)
