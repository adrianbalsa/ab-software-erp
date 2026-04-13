from __future__ import annotations

import base64
import datetime
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from app.db.supabase import SupabaseAsync
from app.core.crypto import pii_crypto
from app.services.aeat_qr_service import (
    build_srei_verifactu_url,
    build_tike_verifactu_url,
    qr_png_bytes_from_url,
)

# Semilla de cadena de huellas ``fingerprint`` (primera factura finalizada de la empresa).
# Distinta del encadenamiento ``hash_registro`` al emitir (allí ``hash_anterior`` vacío en el primero).
VERIFACTU_CHAIN_SEED_HEX = hashlib.sha256(
    b"VERIFACTU|FINGERPRINT_CHAIN|GENESIS|AB_SCANNER|v1"
).hexdigest()

# Génesis para cadena de ``hash_factura`` (inalterabilidad): cadena de ceros (64 hex = 256 bits).
# Primera factura del tenant: ``hash_anterior`` = génesis; ``hash_factura`` = SHA-256(datos|génesis).
VERIFACTU_INVOICE_GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class EslabonFacturaAnterior:
    """Encadenamiento VeriFactu: último hash y siguiente número secuencial."""

    hash_anterior: str | None
    siguiente_secuencial: int


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class VerifactuService:
    """
    Minimal, DB-agnostic VeriFactu helpers.

    Important:
    - We DON'T assume columns exist in `facturas`.
    - We provide deterministic hashing and a way to fetch previous hash/sequential
      if your schema includes those columns.
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    # -------------------------------------------------------------------------
    # Normalización determinista (misma entrada canónica → mismo hash)
    # -------------------------------------------------------------------------

    @staticmethod
    def _norm_str(value: Any) -> str:
        return str(value if value is not None else "").strip()

    @staticmethod
    def _norm_nif(value: Any) -> str:
        """NIF/CIF: sin espacios, mayúsculas (determinista frente a espacios/caja)."""
        return "".join(VerifactuService._norm_str(value).split()).upper()

    @staticmethod
    def _norm_fecha_iso(value: Any) -> str:
        """
        Fecha de factura en ``YYYY-MM-DD`` (primeros 10 caracteres si ya viene en ISO).
        """
        raw = VerifactuService._norm_str(value)
        if len(raw) >= 10 and _ISO_DATE_RE.match(raw):
            return raw[:10]
        try:
            if isinstance(value, datetime.datetime):
                return value.date().isoformat()
            if isinstance(value, datetime.date):
                return value.isoformat()
        except Exception:
            pass
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.datetime.strptime(raw[:10], fmt).date().isoformat()
            except ValueError:
                continue
        return raw[:10] if len(raw) >= 10 else raw

    @staticmethod
    def _norm_hash_anterior(value: str | None) -> str | None:
        """Hash previo: solo trim; se respeta la caja tal como se persistió (hex SHA-256)."""
        if value is None:
            return None
        t = str(value).strip()
        return t if t else None

    @staticmethod
    def generate_invoice_hash(invoice_data: dict[str, Any], previous_hash: str | None) -> str:
        """
        Huella de inalterabilidad para ``public.facturas.hash_factura`` (cadena dependiente del anterior).

        Concatena (determinista): número, fecha ISO, NIF emisor, total con 2 decimales, y ``previous_hash``.
        Si ``previous_hash`` viene vacío o ``None``, se usa ``VERIFACTU_INVOICE_GENESIS_HASH``
        como semilla de cadena para la primera factura.
        """
        num = VerifactuService._norm_str(
            invoice_data.get("num_factura") or invoice_data.get("numero_factura")
        )
        fecha = VerifactuService._norm_fecha_iso(
            invoice_data.get("fecha_emision") or invoice_data.get("fecha")
        )
        nif_e = VerifactuService._norm_nif(
            invoice_data.get("nif_emisor") or invoice_data.get("nif_empresa")
        )
        try:
            total = float(invoice_data.get("total_factura") or invoice_data.get("total") or 0.0)
        except (TypeError, ValueError):
            total = 0.0
        tot = "{:.2f}".format(total)
        prev = str(previous_hash or "").strip()
        if not prev:
            prev = VERIFACTU_INVOICE_GENESIS_HASH
        cadena = f"{num}|{fecha}|{nif_e}|{tot}|{prev}"
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest()

    @staticmethod
    def _cadena_para_hash_verifactu(
        *,
        nif_empresa: str,
        nif_cliente: str,
        num_factura: str,
        fecha: str,
        total: float,
        hash_anterior: str | None = None,
        tipo_factura: str | None = None,
        num_factura_rectificada: str | None = None,
    ) -> str:
        """
        Cadena exacta que alimenta SHA-256 (determinista).

        ``NIF_E + NIF_C + Num + Fecha_ISO + Total_00 + [|T:TIPO][|RECT:NUM_ORIG] + HashAnterior_hex]``

        Los segmentos opcionales ``|T:`` y ``|RECT:`` solo se añaden en rectificativas
        (R1, …) para atar el registro al tipo y al número de factura corregida [cite: 2026-03-22].
        Si se omiten, el comportamiento coincide con el hash histórico F1.
        """
        nif_e = VerifactuService._norm_nif(nif_empresa)
        nif_c = VerifactuService._norm_nif(nif_cliente)
        num = VerifactuService._norm_str(num_factura)
        fe = VerifactuService._norm_fecha_iso(fecha)
        tot = "{:.2f}".format(float(total))
        hprev = VerifactuService._norm_hash_anterior(hash_anterior)
        cadena = nif_e + nif_c + num + fe + tot
        t_norm = VerifactuService._norm_str(tipo_factura).upper()
        if t_norm:
            cadena += "|T:" + t_norm
        rect_norm = VerifactuService._norm_str(num_factura_rectificada)
        if rect_norm:
            cadena += "|RECT:" + rect_norm
        if hprev:
            cadena += hprev
        return cadena

    @staticmethod
    def generar_hash_factura(
        *,
        nif_empresa: str,
        nif_cliente: str,
        num_factura: str,
        fecha: str,
        total: float,
        hash_anterior: str | None = None,
        tipo_factura: str | None = None,
        num_factura_rectificada: str | None = None,
    ) -> str:
        """
        Huella VeriFactu (cadena normalizada, SHA-256 en hex).

        ``Hash = SHA256(NIF_Emisor + NIF_Cliente + Num_Factura + Fecha + Total + [|T:][|RECT:] + Hash_Anterior)``

        - *Total*: importe con dos decimales (incluye signo en rectificativas, p. ej. ``-123.45``).
        - *Hash_Anterior*: en R1 suele ser el ``hash_registro`` de la factura **rectificada** (F1).
        """
        cadena = VerifactuService._cadena_para_hash_verifactu(
            nif_empresa=nif_empresa,
            nif_cliente=nif_cliente,
            num_factura=num_factura,
            fecha=fecha,
            total=total,
            hash_anterior=hash_anterior,
            tipo_factura=tipo_factura,
            num_factura_rectificada=num_factura_rectificada,
        )
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest()

    async def try_obtener_hash_anterior(self, *, empresa_id: str) -> str | None:
        """
        Último hash de encadenamiento: **misma fila** que el último ``numero_secuencial``.
        Prefiere ``hash_factura``, si no ``hash_registro``. Si no hay facturas, ``None``.
        """
        prev, _seq = await self._ultima_factura_cadena_row(empresa_id=empresa_id)
        return prev

    async def try_obtener_numero_secuencial(self, *, empresa_id: str) -> int | None:
        _prev, next_seq = await self._ultima_factura_cadena_row(empresa_id=empresa_id)
        return next_seq

    async def _ultima_factura_cadena_row(self, *, empresa_id: str) -> tuple[str | None, int]:
        """
        Una sola lectura: última factura emitida por empresa (orden fiscal).

        - ``hash`` para encadenar el **siguiente** registro: preferir ``hash_factura``, si no ``hash_registro``.
        - ``siguiente_secuencial``: ``max(numero_secuencial)+1``, o 1 si no hay filas / es nulo.

        Desempate: ``fecha_emision`` DESC, ``id`` DESC.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return None, 1
        try:
            q = (
                self._db.table("facturas")
                .select("huella_hash, hash_registro, hash_factura, numero_secuencial, fecha_emision, id")
                .eq("empresa_id", eid)
                .eq("bloqueado", True)
                .order("numero_secuencial", desc=True)
                .order("fecha_emision", desc=True)
                .order("id", desc=True)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return None, 1
            row = rows[0]
            raw = row.get("huella_hash") or row.get("hash_factura") or row.get("hash_registro")
            h = VerifactuService._norm_hash_anterior(str(raw) if raw is not None else None)
            val = row.get("numero_secuencial")
            try:
                last_seq = int(val) if val is not None else 0
            except (TypeError, ValueError):
                last_seq = 0
            next_seq = last_seq + 1 if last_seq > 0 else 1
            return h, next_seq
        except Exception:
            return None, 1

    async def _hash_factura_por_secuencial(
        self, *, empresa_id: str, numero_secuencial: int
    ) -> str | None:
        """Hash almacenado de la factura con ``numero_secuencial`` dado (encadenamiento)."""
        eid = str(empresa_id or "").strip()
        if not eid:
            return None
        try:
            q = (
                self._db.table("facturas")
                .select("huella_hash, hash_factura, hash_registro")
                .eq("empresa_id", eid)
                .eq("numero_secuencial", int(numero_secuencial))
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return None
            raw = (
                rows[0].get("huella_hash")
                or rows[0].get("hash_factura")
                or rows[0].get("hash_registro")
            )
            return VerifactuService._norm_hash_anterior(str(raw) if raw is not None else None)
        except Exception:
            return None

    async def verificar_cadena_facturas(
        self,
        *,
        empresa_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Recorre las últimas ``limit`` facturas (por ``numero_secuencial`` desc), re-calcula
        ``generate_invoice_hash`` y comprueba coherencia con ``hash_anterior`` y ``hash_factura``.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return {"ok": False, "error": "empresa_id vacío", "revisadas": 0, "discrepancies": []}

        lim = max(1, min(500, int(limit)))
        try:
            q = (
                self._db.table("facturas")
                .select(
                    "id,numero_secuencial,num_factura,numero_factura,fecha_emision,"
                    "nif_emisor,total_factura,huella_hash,hash_factura,hash_registro,huella_anterior,hash_anterior"
                )
                .eq("empresa_id", eid)
                .order("numero_secuencial", desc=True)
                .order("id", desc=True)
                .limit(lim)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = list((res.data or []) if hasattr(res, "data") else [])
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "empresa_id": eid,
                "revisadas": 0,
                "discrepancies": [],
            }

        rows.reverse()
        discrepancies: list[dict[str, Any]] = []

        if not rows:
            return {
                "ok": True,
                "empresa_id": eid,
                "revisadas": 0,
                "discrepancies": [],
            }

        first = rows[0]
        try:
            seq0 = int(first.get("numero_secuencial") or 0)
        except (TypeError, ValueError):
            seq0 = 0

        if seq0 <= 1:
            prev_hash = VERIFACTU_INVOICE_GENESIS_HASH
        else:
            fetched = await self._hash_factura_por_secuencial(
                empresa_id=eid, numero_secuencial=seq0 - 1
            )
            prev_hash = fetched if fetched else VERIFACTU_INVOICE_GENESIS_HASH

        for row in rows:
            ha_raw = row.get("huella_anterior") if row.get("huella_anterior") is not None else row.get("hash_anterior")
            ha = str(ha_raw if ha_raw is not None else "").strip()
            if ha.lower() != prev_hash.lower():
                discrepancies.append(
                    {
                        "factura_id": row.get("id"),
                        "tipo": "hash_anterior",
                        "esperado": prev_hash,
                        "almacenado": ha or None,
                    }
                )

            raw_nif = row.get("nif_emisor")
            nif_plain = ""
            if raw_nif is not None:
                rn = str(raw_nif).strip()
                nif_plain = pii_crypto.decrypt_pii(rn) or rn

            num = str(row.get("num_factura") or row.get("numero_factura") or "").strip()
            inv = {
                "num_factura": num,
                "fecha_emision": row.get("fecha_emision"),
                "nif_emisor": nif_plain,
                "total_factura": row.get("total_factura"),
            }
            expected = VerifactuService.generate_invoice_hash(inv, prev_hash)
            stored = str(
                row.get("huella_hash")
                or row.get("hash_factura")
                or row.get("hash_registro")
                or ""
            ).strip()
            if stored.lower() != expected.lower():
                discrepancies.append(
                    {
                        "factura_id": row.get("id"),
                        "tipo": "hash_factura",
                        "esperado": expected,
                        "almacenado": stored or None,
                    }
                )

            prev_hash = stored if stored else expected

        return {
            "ok": len(discrepancies) == 0,
            "empresa_id": eid,
            "revisadas": len(rows),
            "discrepancies": discrepancies,
        }

    @staticmethod
    def fingerprint_desde_eslabon_finalizado(
        *,
        prev_fingerprint_final: str | None,
        nif_emisor: str,
        nif_cliente: str,
        num_factura: str,
        fecha_emision: str,
        total_factura: float,
        tipo_factura: str | None = None,
        num_factura_rectificada: str | None = None,
    ) -> tuple[str, str | None]:
        """
        ``(fingerprint, prev_fingerprint)`` a partir del último eslabón **ya finalizado**
        (o ``None`` si no hay ninguno → semilla ``VERIFACTU_CHAIN_SEED_HEX`` como hash anterior interno).
        """
        prev_norm = VerifactuService._norm_hash_anterior(prev_fingerprint_final)
        hash_anterior = prev_norm if prev_norm else VERIFACTU_CHAIN_SEED_HEX
        tipo = str(tipo_factura).strip().upper() if tipo_factura else None
        tipo_arg = tipo if tipo == "R1" else None
        rect_arg: str | None = None
        if tipo_arg == "R1" and num_factura_rectificada:
            rect_arg = str(num_factura_rectificada).strip() or None

        fp = VerifactuService.generar_hash_factura(
            nif_empresa=nif_emisor,
            nif_cliente=nif_cliente,
            num_factura=num_factura,
            fecha=str(fecha_emision),
            total=float(total_factura),
            hash_anterior=hash_anterior,
            tipo_factura=tipo_arg,
            num_factura_rectificada=rect_arg,
        )
        return fp, prev_norm

    async def ultima_fingerprint_factura_finalizada(self, *, empresa_id: str) -> str | None:
        """
        Huella ``fingerprint`` de la última factura con ``is_finalized`` para la empresa
        (orden fiscal: ``numero_secuencial``, ``fecha_emision``, ``id``).
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return None
        try:
            q = (
                self._db.table("facturas")
                .select("fingerprint,numero_secuencial,fecha_emision,id")
                .eq("empresa_id", eid)
                .eq("is_finalized", True)
                .not_.is_("fingerprint", "null")  # type: ignore[attr-defined]
                .order("numero_secuencial", desc=True)
                .order("fecha_emision", desc=True)
                .order("id", desc=True)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return None
            fp = rows[0].get("fingerprint")
            t = str(fp).strip() if fp is not None else ""
            return t if t else None
        except Exception:
            return None

    async def chain_invoice(
        self,
        *,
        empresa_id: str,
        nif_emisor: str,
        nif_cliente: str,
        num_factura: str,
        fecha_emision: str,
        total_factura: float,
        tipo_factura: str | None = None,
        num_factura_rectificada: str | None = None,
    ) -> tuple[str, str | None]:
        """
        Igual que ``fingerprint_desde_eslabon_finalizado`` pero resuelve ``prev_fingerprint``
        leyendo la última factura finalizada de la empresa.
        """
        prev_fp = await self.ultima_fingerprint_factura_finalizada(empresa_id=empresa_id)
        return self.fingerprint_desde_eslabon_finalizado(
            prev_fingerprint_final=prev_fp,
            nif_emisor=nif_emisor,
            nif_cliente=nif_cliente,
            num_factura=num_factura,
            fecha_emision=fecha_emision,
            total_factura=total_factura,
            tipo_factura=tipo_factura,
            num_factura_rectificada=num_factura_rectificada,
        )

    async def generate_aeat_url(self, invoice_id: int) -> str:
        """
        URL pública VeriFactu (SREI) para la factura: NIF emisor descifrado, número-serie,
        fecha e importe total.
        """
        fid = int(invoice_id)
        if fid < 1:
            raise ValueError("Factura no encontrada")
        res: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", fid).limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Factura no encontrada")
        fr = dict(rows[0])
        eid = str(fr.get("empresa_id") or "").strip()

        nif_em = ""
        raw_ne = fr.get("nif_emisor")
        if raw_ne is not None:
            rn = str(raw_ne).strip()
            nif_em = (pii_crypto.decrypt_pii(rn) or rn).strip()
        if not nif_em and eid:
            try:
                res_e: Any = await self._db.execute(
                    self._db.table("empresas").select("nif").eq("id", eid).limit(1)
                )
                er = (res_e.data or []) if hasattr(res_e, "data") else []
                if er:
                    raw = er[0].get("nif")
                    if raw is not None:
                        s = str(raw).strip()
                        nif_em = (pii_crypto.decrypt_pii(s) or s).strip()
            except Exception:
                pass

        num_s = str(fr.get("num_factura") or fr.get("numero_factura") or "").strip()
        fe_str = self._norm_fecha_iso(fr.get("fecha_emision"))
        try:
            total = float(fr.get("total_factura") or 0.0)
        except (TypeError, ValueError):
            total = 0.0
        huella = str(
            fr.get("huella_hash")
            or fr.get("hash_registro")
            or fr.get("hash_factura")
            or fr.get("fingerprint")
            or ""
        ).strip()

        if not nif_em or not num_s or not fe_str:
            raise ValueError(
                "Datos insuficientes para URL VeriFactu (NIF emisor, número de factura o fecha)"
            )
        return build_srei_verifactu_url(
            nif_em,
            num_s,
            fe_str,
            total,
            huella_hash=huella,
        )

    async def generate_verifactu_qr(
        self,
        *,
        nif_emisor: str,
        num_factura: str,
        fecha: str,
        importe_total: float,
        fingerprint: str,
        huella_hash: str | None = None,
        storage_bucket: str | None = "facturas",
        storage_path: str | None = None,
    ) -> dict[str, str | None]:
        """
        URL SREI VeriFactu y PNG en base64; opcionalmente sube el PNG a Supabase Storage.
        El parámetro ``fingerprint`` se mantiene por compatibilidad de firma pero la URL
        SREI no lo incluye en la URL.
        """
        huella = str(huella_hash or fingerprint or "").strip()
        url = build_srei_verifactu_url(
            nif_emisor,
            num_factura,
            fecha,
            importe_total,
            huella_hash=huella,
        )
        png = qr_png_bytes_from_url(url)
        b64 = base64.b64encode(png).decode("ascii")
        uploaded: str | None = None
        if storage_bucket and storage_path:
            try:
                await self._db.storage_upload(
                    bucket=storage_bucket,
                    path=storage_path,
                    content=png,
                    content_type="image/png",
                )
                uploaded = storage_path
            except Exception:
                uploaded = None
        return {
            "verification_url": url,
            "qr_png_base64": b64,
            "storage_path": uploaded,
        }

    async def obtener_ultimo_hash_y_secuencial(self, *, empresa_id: str) -> EslabonFacturaAnterior:
        """
        Recupera el eslabón anterior para la cadena VeriFactu en `facturas`:

        - ``hash_anterior``: ``hash_factura`` de la última factura emitida; si no hay facturas,
          **génesis** (``VERIFACTU_INVOICE_GENESIS_HASH``).
        - ``siguiente_secuencial``: siguiente entero (1 si no hay facturas previas).
        """
        hash_anterior, siguiente = await self._ultima_factura_cadena_row(empresa_id=empresa_id)
        chain_prev = (
            VERIFACTU_INVOICE_GENESIS_HASH if hash_anterior is None else hash_anterior
        )
        return EslabonFacturaAnterior(
            hash_anterior=chain_prev,
            siguiente_secuencial=int(siguiente),
        )

    # ---------------------------------------------------------------------------------
    # Legacy-like methods migrated from `Scanner/services/verifactu_service.py`.
    #
    # These helpers are intentionally best-effort: your current DB schema may differ.
    # ---------------------------------------------------------------------------------

    async def obtener_numero_secuencial(self, empresa_id: str) -> int | None:
        """
        Legacy: obtiene numero_secuencial desde tabla `presupuestos`.
        """
        try:
            q = (
                self._db.table("presupuestos")
                .select("numero_secuencial")
                .eq("empresa_id", empresa_id)
                .not_.is_("numero_secuencial", "null")  # type: ignore[attr-defined]
                .order("numero_secuencial", desc=True)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if rows:
                return int(rows[0]["numero_secuencial"]) + 1
            return 1
        except Exception:
            return None

    async def obtener_hash_anterior(self, empresa_id: str) -> str | None:
        """
        Legacy: obtiene hash_factura anterior desde `presupuestos`.
        """
        try:
            q = (
                self._db.table("presupuestos")
                .select("hash_factura")
                .eq("empresa_id", empresa_id)
                .eq("estado", "Facturado")
                .not_.is_("hash_factura", "null")  # type: ignore[attr-defined]
                .order("numero_secuencial", desc=True)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if rows:
                return rows[0].get("hash_factura")
            return None
        except Exception:
            return None

    def generar_hash_factura_desde_datos(
        self,
        datos_factura: dict[str, Any],
        hash_anterior: str | None = None,
    ) -> str | None:
        """
        Legacy: misma cadena normalizada que ``generar_hash_factura`` (determinista).
        """
        try:
            return self.generar_hash_factura(
                nif_empresa=str(datos_factura["nif_empresa"]),
                nif_cliente=str(datos_factura["nif_cliente"]),
                num_factura=str(datos_factura["num_factura"]),
                fecha=str(datos_factura["fecha"]),
                total=float(datos_factura["total"]),
                hash_anterior=hash_anterior,
                tipo_factura=datos_factura.get("tipo_factura"),
                num_factura_rectificada=datos_factura.get("num_factura_rectificada"),
            )
        except Exception:
            return None

    async def registrar_evento(
        self,
        *,
        accion: str,
        registro_id: str,
        detalles: dict[str, Any],
        empresa_id: str,
        usuario_id: str | None = None,
    ) -> None:
        """
        Best-effort: evento VeriFactu en ``auditoria`` (trazabilidad: acción, registro, detalles, usuario).

        ``detalles`` suele incluir ``num_factura`` y ``hash_registro``; ``usuario_id`` se añade al JSON.
        """
        try:
            cambios: dict[str, Any] = {
                **detalles,
                "usuario_id": usuario_id,
            }
            payload: dict[str, Any] = {
                "empresa_id": empresa_id,
                "accion": accion,
                "tabla": "facturas",
                "registro_id": str(registro_id),
                "cambios": json.dumps(cambios, ensure_ascii=False),
                "fecha": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            }
            await self._db.execute(self._db.table("auditoria").insert(payload))
        except Exception:
            return

    async def registrar_auditoria(
        self,
        accion: str,
        tabla: str,
        registro_id: Any,
        cambios: dict[str, Any],
        empresa_id: str | None = None,
    ) -> None:
        """
        Legacy (best-effort): inserta en `auditoria`.
        """
        try:
            payload = {
                "accion": accion,
                "tabla": tabla,
                "registro_id": str(registro_id),
                "cambios": json.dumps(cambios),
                "fecha": str(datetime.datetime.now()),
                "empresa_id": empresa_id or str(cambios.get("empresa_id") or "unknown"),
            }
            await self._db.execute(self._db.table("auditoria").insert(payload))
        except Exception:
            return

    async def emitir_factura_desde_presupuesto(
        self,
        presupuesto_row: dict[str, Any],
        prefijo_serie: str,
        nif_emisor: str,
    ) -> dict[str, Any]:
        """
        Legacy: genera campos de factura desde un registro de `presupuestos`.
        """
        try:
            empresa_id = presupuesto_row.get("empresa_id")
            if not empresa_id:
                return {"success": False, "error": "Falta empresa_id"}

            numero_secuencial = await self.obtener_numero_secuencial(str(empresa_id))
            if not numero_secuencial:
                return {"success": False, "error": "Error numero secuencial"}

            hash_anterior = await self.obtener_hash_anterior(str(empresa_id))
            anio = datetime.date.today().year
            num_factura = "{}-{}-{:06d}".format(prefijo_serie, anio, numero_secuencial)

            fecha = presupuesto_row.get("fecha_factura") or presupuesto_row.get("fecha")
            base = float(presupuesto_row.get("total_neto") or 0)
            impuestos = float(presupuesto_row.get("impuestos") or 0)
            total = float(
                presupuesto_row.get("total_final")
                or presupuesto_row.get("total")
                or (base + impuestos)
            )

            nif_empresa_plain = pii_crypto.decrypt_pii(nif_emisor) or nif_emisor
            raw_nif_cliente = presupuesto_row.get("nif_cliente") or ""
            nif_cliente_plain = (
                pii_crypto.decrypt_pii(str(raw_nif_cliente).strip())
                or str(raw_nif_cliente).strip()
            )

            datos_hash = {
                "nif_empresa": nif_empresa_plain,
                "nif_cliente": nif_cliente_plain,
                "num_factura": num_factura,
                "fecha": str(fecha),
                "total": total,
            }
            hash_factura = self.generar_hash_factura_desde_datos(datos_hash, hash_anterior)
            if not hash_factura:
                return {"success": False, "error": "Error generando hash"}

            return {
                "success": True,
                "num_factura": num_factura,
                "hash_factura": hash_factura,
                "hash_anterior": hash_anterior,
                "fecha_factura": fecha,
                "total_neto": base,
                "impuestos": impuestos,
                "total_final": total,
                "numero_secuencial": numero_secuencial,
                "bloqueado": True,
                "estado": "Facturado",
                "tipo_factura": "NORMAL",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verificar_hash(
        self,
        hash_factura: str,
        datos_factura: dict[str, Any],
        hash_anterior: str | None = None,
    ) -> bool:
        """
        Legacy: verifica el hash calculado (comparación hex case-insensitive).
        """
        expected = self.generar_hash_factura_desde_datos(datos_factura, hash_anterior)
        if expected is None:
            return False
        return str(expected).strip().lower() == str(hash_factura).strip().lower()

    async def anular_factura(
        self,
        factura_id: str,
        usuario: str,
        motivo: str,
    ) -> dict[str, Any]:
        """
        Legacy (best-effort): anula una factura en tabla `presupuestos`.
        """
        try:
            res: Any = await self._db.execute(
                self._db.table("presupuestos")
                .select("num_factura,empresa_id,numero_secuencial")
                .eq("id", factura_id)
            )
            if not getattr(res, "data", None):
                return {"success": False, "error": "Factura no encontrada"}

            factura = res.data[0]
            await self._db.execute(
                self._db.table("presupuestos").update(
                    {
                        "estado": "Anulado",
                        "tipo_factura": "ANULACION",
                        "observaciones": "ANULADA por {} | Motivo: {}".format(usuario, motivo),
                        "bloqueado": True,
                    }
                ).eq("id", factura_id)
            )

            await self.registrar_auditoria(
                accion="ANULAR_FACTURA",
                tabla="presupuestos",
                registro_id=factura_id,
                cambios={
                    "num_factura": factura.get("num_factura"),
                    "usuario": usuario,
                    "motivo": motivo,
                    "empresa_id": factura.get("empresa_id"),
                },
                empresa_id=str(factura.get("empresa_id") or "unknown"),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def crear_factura_rectificativa(
        self,
        factura_origen_id: str,
        empresa_id: str,
        cambios: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Legacy (best-effort): crea una factura rectificativa en `presupuestos`.
        """
        try:
            res: Any = await self._db.execute(
                self._db.table("presupuestos").select("*").eq("id", factura_origen_id)
            )
            if not getattr(res, "data", None):
                return {"success": False, "error": "Factura original no encontrada"}

            factura_original = res.data[0]
            numero_secuencial = await self.obtener_numero_secuencial(empresa_id)
            if not numero_secuencial:
                return {"success": False, "error": "Error generando numero secuencial"}

            anio = datetime.date.today().year
            num_factura_rect = "RECT-{}-{:06d}".format(anio, numero_secuencial)

            nif_empresa = factura_original.get("nif_empresa")
            nif_empresa_plain = (
                pii_crypto.decrypt_pii(str(nif_empresa).strip()) or str(nif_empresa).strip()
            ) if nif_empresa is not None else ""

            if not nif_empresa_plain:
                res_emp: Any = await self._db.execute(
                    self._db.table("empresas").select("nif").eq("id", empresa_id).limit(1)
                )
                emp_rows: list[dict[str, Any]] = (
                    res_emp.data or [] if hasattr(res_emp, "data") else []
                )
                raw_emp_nif = emp_rows[0].get("nif", "") if emp_rows else ""
                nif_empresa_plain = (
                    pii_crypto.decrypt_pii(str(raw_emp_nif).strip()) or str(raw_emp_nif).strip()
                )

            hash_anterior = await self.obtener_hash_anterior(empresa_id)

            nuevo_total = float(cambios["total"])
            total_neto = float(cambios.get("total_neto") or (nuevo_total / 1.21))
            impuestos = float(cambios.get("impuestos") or (nuevo_total - total_neto))

            raw_nif_cliente = cambios.get("nif_cliente", "") or factura_original.get("nif_cliente", "") or ""
            nif_cliente_plain = (
                pii_crypto.decrypt_pii(str(raw_nif_cliente).strip())
                or str(raw_nif_cliente).strip()
            )

            datos_hash = {
                "nif_empresa": nif_empresa_plain,
                "nif_cliente": nif_cliente_plain,
                "num_factura": num_factura_rect,
                "fecha": str(datetime.date.today()),
                "total": nuevo_total,
            }
            hash_rect = self.generar_hash_factura_desde_datos(datos_hash, hash_anterior)

            await self._db.execute(
                self._db.table("presupuestos").insert(
                    {
                        "empresa_id": empresa_id,
                        "cliente": cambios.get("cliente", factura_original.get("cliente")),
                        "nif_cliente": pii_crypto.encrypt_pii(nif_cliente_plain),
                        "titulo": "RECTIFICATIVA de {}".format(
                            factura_original.get("num_factura", "N/A")
                        ),
                        "total_neto": round(total_neto, 2),
                        "impuestos": round(impuestos, 2),
                        "total_final": nuevo_total,
                        "iva_porcentaje": factura_original.get("iva_porcentaje", 21.0),
                        "moneda": factura_original.get("moneda", "EUR"),
                        "estado": "Facturado",
                        "tipo_factura": "RECTIFICATIVA",
                        "num_factura": num_factura_rect,
                        "numero_secuencial": numero_secuencial,
                        "fecha": str(datetime.date.today()),
                        "fecha_factura": str(datetime.date.today()),
                        "hash_factura": hash_rect,
                        "hash_anterior": hash_anterior,
                        "nif_empresa": pii_crypto.encrypt_pii(nif_empresa_plain),
                        "observaciones": "Rectificativa de {} | {}".format(
                            factura_original.get("num_factura"), cambios.get("motivo", "")
                        ),
                        "bloqueado": True,
                        "items": factura_original.get("items", "[]"),
                    }
                )
            )

            await self._db.execute(
                self._db.table("presupuestos").update(
                    {"observaciones": "RECTIFICADA por {}".format(num_factura_rect)}
                ).eq("id", factura_origen_id)
            )

            await self.registrar_auditoria(
                accion="CREAR_FACTURA_RECTIFICATIVA",
                tabla="presupuestos",
                registro_id=factura_origen_id,
                cambios={
                    "num_factura_rect": num_factura_rect,
                    "hash": (hash_rect or "")[:16] + "...",
                    "factura_origen": factura_original.get("num_factura"),
                    "empresa_id": empresa_id,
                },
                empresa_id=empresa_id,
            )

            return {"success": True, "num_factura": num_factura_rect, "hash": hash_rect}
        except Exception as e:
            return {"success": False, "error": str(e)}

