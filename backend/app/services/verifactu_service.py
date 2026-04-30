from __future__ import annotations

import base64
import datetime
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from jinja2 import Environment, FileSystemLoader

from app.db.supabase import SupabaseAsync
from app.core.config import get_settings
from app.core.crypto import pii_crypto
from app.core.fiscal_logic import fiscal_amount_string_two_decimals
from app.core.verifactu_hashing import (
    CanonicalHashService,
    VerifactuCadena,
    generar_hash_factura_oficial,
    norm_fecha_expedicion_verifactu,
    norm_nif_emisor_verifactu,
)
from app.services.aeat_soap_client import AeatSoapClient, AeatSubmissionStatus
from app.services.aeat_qr_service import (
    build_srei_verifactu_url,
    qr_png_bytes_from_url,
)
from app.services.verifactu_sender import envolver_soap12, url_envio_efectiva
from app.services.verifactu_genesis import get_verifactu_genesis_hash_for_issuer

@dataclass(frozen=True, slots=True)
class EslabonFacturaAnterior:
    """Encadenamiento VeriFactu: último hash y siguiente número secuencial."""

    hash_anterior: str | None
    siguiente_secuencial: int


_VERIFACTU_NULL_CHAIN_HASH = "0" * 64


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
        templates_dir = Path(__file__).resolve().parents[1] / "templates"
        self._jinja = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # -------------------------------------------------------------------------
    # Normalización determinista (misma entrada canónica → mismo hash)
    # -------------------------------------------------------------------------

    @staticmethod
    def null_chain_hash() -> str:
        """Valor nulo estandarizado para primer eslabón de cadena VeriFactu."""
        return _VERIFACTU_NULL_CHAIN_HASH

    @staticmethod
    def _norm_str(value: Any) -> str:
        return str(value if value is not None else "").strip()

    @staticmethod
    def _norm_nif(value: Any) -> str:
        """NIF/CIF: sin espacios, mayúsculas (determinista frente a espacios/caja)."""
        return norm_nif_emisor_verifactu(value)

    @staticmethod
    def _norm_fecha_iso(value: Any) -> str:
        """
        Fecha de factura en ``YYYY-MM-DD`` (primeros 10 caracteres si ya viene en ISO).
        """
        return norm_fecha_expedicion_verifactu(value)

    @staticmethod
    def _norm_hash_anterior(value: str | None) -> str | None:
        """Hash previo: solo trim; se respeta la caja tal como se persistió (hex SHA-256)."""
        if value is None:
            return None
        t = str(value).strip()
        return t if t else None

    @staticmethod
    def generar_huella_verifactu(
        *,
        nif_emisor: str,
        numero_serie_factura: str,
        fecha_expedicion: str | datetime.date,
        importe_total: Decimal | str | int,
        huella_hash_anterior: str,
    ) -> str:
        """
        Huella encadenada VeriFactu (SHA-256 HEX en MAYÚSCULAS). Delegación única en
        ``CanonicalHashService.generate_verifactu_hash``.
        """
        prev = VerifactuService._norm_hash_anterior(huella_hash_anterior)
        if not prev:
            raise ValueError("huella_hash_anterior vacío")
        return CanonicalHashService.generate_verifactu_hash(
            nif_emisor=nif_emisor,
            num_serie_factura=numero_serie_factura,
            fecha_expedicion=fecha_expedicion,
            importe_total=importe_total,
            huella_anterior=prev,
        )

    @staticmethod
    def generate_invoice_hash(invoice_data: dict[str, Any], previous_hash: str | None) -> str:
        """
        Huella de inalterabilidad para ``public.facturas.hash_factura`` (cadena dependiente del anterior).

        Delega en ``generar_hash_factura_oficial`` (HUELLA_EMISION).
        """
        return generar_hash_factura_oficial(
            VerifactuCadena.HUELLA_EMISION, invoice_data, previous_hash
        )

    @staticmethod
    def _cadena_para_hash_verifactu(
        *,
        nif_empresa: str,
        nif_cliente: str,
        num_factura: str,
        fecha: str,
        total: Any,
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
        tot = fiscal_amount_string_two_decimals(total)
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
        total: Any,
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

    async def obtener_huella_anterior_por_serie(
        self,
        *,
        empresa_id: str,
        serie: str,
    ) -> str:
        """
        Recupera la huella de la última factura emitida de la misma empresa y serie.
        Si no existe, devuelve valor nulo estandarizado (64 ceros).
        """
        eid = str(empresa_id or "").strip()
        serie_norm = str(serie or "").strip()
        if not eid:
            raise ValueError("empresa_id vacío")
        if not serie_norm:
            raise ValueError("serie vacía")
        try:
            q = (
                self._db.table("facturas")
                .select("huella_hash, hash_factura, hash_registro, numero_secuencial, fecha_emision, id")
                .eq("empresa_id", eid)
                .eq("bloqueado", True)
                .like("num_factura", f"{serie_norm}-%")
                .order("numero_secuencial", desc=True)
                .order("fecha_emision", desc=True)
                .order("id", desc=True)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return self.null_chain_hash()
            raw = rows[0].get("huella_hash") or rows[0].get("hash_factura") or rows[0].get("hash_registro")
            prev = VerifactuService._norm_hash_anterior(str(raw) if raw is not None else None)
            return (prev or self.null_chain_hash()).upper()
        except Exception as exc:
            raise RuntimeError(
                "No se pudo recuperar la huella anterior VeriFactu por serie"
            ) from exc

    async def obtener_eslabon_anterior_por_serie(
        self,
        *,
        empresa_id: str,
        serie: str,
    ) -> EslabonFacturaAnterior:
        """
        Recupera hash previo y siguiente secuencial de la última factura emitida
        por ``empresa_id + serie``. Si no existe, inicia con 64 ceros y secuencial 1.
        """
        eid = str(empresa_id or "").strip()
        serie_norm = str(serie or "").strip()
        if not eid:
            raise ValueError("empresa_id vacío")
        if not serie_norm:
            raise ValueError("serie vacía")
        try:
            q = (
                self._db.table("facturas")
                .select("huella_hash, hash_factura, hash_registro, numero_secuencial, fecha_emision, id")
                .eq("empresa_id", eid)
                .eq("bloqueado", True)
                .like("num_factura", f"{serie_norm}-%")
                .order("numero_secuencial", desc=True)
                .order("fecha_emision", desc=True)
                .order("id", desc=True)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if not rows:
                return EslabonFacturaAnterior(
                    hash_anterior=self.null_chain_hash(),
                    siguiente_secuencial=1,
                )
            row = rows[0]
            raw = row.get("huella_hash") or row.get("hash_factura") or row.get("hash_registro")
            prev = VerifactuService._norm_hash_anterior(str(raw) if raw is not None else None)
            try:
                last_seq = int(row.get("numero_secuencial") or 0)
            except (TypeError, ValueError):
                last_seq = 0
            next_seq = last_seq + 1 if last_seq > 0 else 1
            return EslabonFacturaAnterior(
                hash_anterior=(prev or self.null_chain_hash()).upper(),
                siguiente_secuencial=next_seq,
            )
        except Exception as exc:
            raise RuntimeError(
                "No se pudo recuperar el eslabón anterior VeriFactu por serie"
            ) from exc

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

        genesis_hash = get_verifactu_genesis_hash_for_issuer(issuer_id=eid)
        if seq0 <= 1:
            prev_hash = genesis_hash
        else:
            fetched = await self._hash_factura_por_secuencial(
                empresa_id=eid, numero_secuencial=seq0 - 1
            )
            prev_hash = fetched if fetched else genesis_hash

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
        genesis_hash: str | None = None,
    ) -> tuple[str, str | None]:
        """
        ``(fingerprint, prev_fingerprint)`` a partir del último eslabón **ya finalizado**
        (o ``None`` si no hay ninguno → ``genesis_hash`` único del emisor como hash anterior interno).
        """
        prev_norm = VerifactuService._norm_hash_anterior(prev_fingerprint_final)
        genesis_norm = VerifactuService._norm_hash_anterior(genesis_hash)
        if not prev_norm and not genesis_norm:
            raise RuntimeError("verifactu_genesis_hash_missing_for_issuer")
        hash_anterior = prev_norm if prev_norm else str(genesis_norm)
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
            total=total_factura,
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
        genesis_hash = get_verifactu_genesis_hash_for_issuer(
            issuer_id=empresa_id,
            issuer_nif=nif_emisor,
        )
        return self.fingerprint_desde_eslabon_finalizado(
            prev_fingerprint_final=prev_fp,
            nif_emisor=nif_emisor,
            nif_cliente=nif_cliente,
            num_factura=num_factura,
            fecha_emision=fecha_emision,
            total_factura=total_factura,
            tipo_factura=tipo_factura,
            num_factura_rectificada=num_factura_rectificada,
            genesis_hash=genesis_hash,
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
        La URL incluye ``hc`` (8 primeros caracteres de ``huella_hash`` o ``fingerprint``).
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
          génesis único del emisor resuelto desde Secret Manager.
        - ``siguiente_secuencial``: siguiente entero (1 si no hay facturas previas).
        """
        hash_anterior, siguiente = await self._ultima_factura_cadena_row(empresa_id=empresa_id)
        chain_prev = (
            get_verifactu_genesis_hash_for_issuer(issuer_id=empresa_id)
            if hash_anterior is None
            else hash_anterior
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
                total=datos_factura["total"],
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
        strict: bool = False,
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
            if strict:
                raise
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

    async def prepare_xml_payload(
        self,
        *,
        factura_row: dict[str, Any],
        empresa_row: dict[str, Any],
        cliente_row: dict[str, Any],
    ) -> dict[str, str]:
        """
        Prepara el payload XML VeriFactu (fragmento interior + SOAP 1.2) con huella canónica.
        """
        nif_emisor = str(factura_row.get("nif_emisor") or empresa_row.get("nif") or "").strip()
        if not nif_emisor:
            raise ValueError("NIF emisor vacío para XML VeriFactu.")
        num_serie = str(factura_row.get("num_factura") or factura_row.get("numero_factura") or "").strip()
        if not num_serie:
            raise ValueError("Número de factura vacío para XML VeriFactu.")
        fecha_raw = str(factura_row.get("fecha_emision") or factura_row.get("fecha") or "").strip()
        fecha_exp = self._norm_fecha_iso(fecha_raw)
        if not fecha_exp:
            raise ValueError("Fecha de expedición inválida para XML VeriFactu.")

        prev_huella = str(
            factura_row.get("huella_anterior")
            or factura_row.get("hash_anterior")
            or ""
        ).strip().upper()
        if not prev_huella:
            empresa_id = str(factura_row.get("empresa_id") or empresa_row.get("id") or "").strip()
            prev_huella = get_verifactu_genesis_hash_for_issuer(
                issuer_id=empresa_id,
                issuer_nif=nif_emisor,
            )

        importe_total = Decimal(str(factura_row.get("total_factura") or "0"))
        huella = CanonicalHashService.generate_verifactu_hash(
            nif_emisor=nif_emisor,
            num_serie_factura=num_serie,
            fecha_expedicion=fecha_exp,
            importe_total=importe_total,
            huella_anterior=prev_huella,
        )

        template = self._jinja.get_template("verifactu_request.xml")
        xml_inner = template.render(
            nif_emisor=nif_emisor,
            num_serie_factura=num_serie,
            fecha_expedicion=fecha_exp,
            importe_total=fiscal_amount_string_two_decimals(importe_total),
            huella=huella,
            nombre_razon_emisor=str(
                empresa_row.get("nombre_comercial") or empresa_row.get("nombre_legal") or nif_emisor
            ).strip(),
            nombre_destinatario=str(cliente_row.get("nombre") or "").strip(),
            nif_destinatario=str(cliente_row.get("nif") or "").strip(),
            timestamp_utc=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            tipo_factura=str(factura_row.get("tipo_factura") or "F1").strip().upper() or "F1",
        ).strip()
        soap_payload = envolver_soap12(xml_inner)
        return {"xml_inner": xml_inner, "soap_payload": soap_payload, "huella": huella}

    async def submit_invoice_to_aeat(self, factura_id: UUID) -> dict[str, Any]:
        """
        Orquesta el envío final a AEAT por mTLS para una factura:
        DB -> XML -> SOAP -> AEAT -> persistencia estado + auditoría.
        """
        settings = get_settings()
        cert_path = (settings.AEAT_CLIENT_CERT_PATH or "").strip()
        key_path = (settings.AEAT_CLIENT_KEY_PATH or "").strip()
        if not cert_path or not key_path:
            raise RuntimeError(
                "Faltan AEAT_CLIENT_CERT_PATH / AEAT_CLIENT_KEY_PATH (.pem). "
                "Use make aeat-prepare-certs y configure .env."
            )

        endpoint = url_envio_efectiva(settings)
        if not endpoint:
            raise RuntimeError("No hay endpoint AEAT configurado (AEAT_VERIFACTU_SUBMIT_URL_TEST/PROD).")

        fid = str(factura_id)
        rf: Any = await self._db.execute(
            self._db.table("facturas").select("*").eq("id", fid).limit(1)
        )
        rows = (rf.data or []) if hasattr(rf, "data") else []
        if not rows:
            raise ValueError("Factura no encontrada.")
        factura = dict(rows[0])

        empresa_id = str(factura.get("empresa_id") or "").strip()
        if not empresa_id:
            raise ValueError("Factura sin empresa_id.")

        re: Any = await self._db.execute(
            self._db.table("empresas").select("*").eq("id", empresa_id).limit(1)
        )
        erows = (re.data or []) if hasattr(re, "data") else []
        if not erows:
            raise ValueError("Empresa no encontrada.")
        empresa = dict(erows[0])

        raw_emp_nif = empresa.get("nif")
        if isinstance(raw_emp_nif, str) and raw_emp_nif.strip():
            empresa["nif"] = pii_crypto.decrypt_pii(raw_emp_nif) or raw_emp_nif
        raw_fac_nif = factura.get("nif_emisor")
        if isinstance(raw_fac_nif, str) and raw_fac_nif.strip():
            factura["nif_emisor"] = pii_crypto.decrypt_pii(raw_fac_nif) or raw_fac_nif

        cliente: dict[str, Any] = {"nif": "", "nombre": ""}
        cid = str(factura.get("cliente") or factura.get("cliente_id") or "").strip()
        if cid:
            rc: Any = await self._db.execute(
                self._db.table("clientes")
                .select("*")
                .eq("id", cid)
                .eq("empresa_id", empresa_id)
                .limit(1)
            )
            crows = (rc.data or []) if hasattr(rc, "data") else []
            if crows:
                cliente = dict(crows[0])
                raw_cli_nif = cliente.get("nif")
                if isinstance(raw_cli_nif, str) and raw_cli_nif.strip():
                    cliente["nif"] = pii_crypto.decrypt_pii(raw_cli_nif) or raw_cli_nif

        payload = await self.prepare_xml_payload(
            factura_row=factura, empresa_row=empresa, cliente_row=cliente
        )
        soap = AeatSoapClient(cert_file=cert_path, key_file=key_path, settings=settings)
        try:
            result = soap.submit_signed_soap(
                service_url=endpoint,
                soap12_body=payload["soap_payload"],
                signed_inner_xml=payload["xml_inner"],
            )
        finally:
            soap.close()

        mapping = {
            AeatSubmissionStatus.ACCEPTED: ("aceptado", "ENVIADA", None),
            AeatSubmissionStatus.ACCEPTED_WITH_ERRORS: ("aceptado_con_errores", "ENVIADA_CON_ERRORES", None),
            AeatSubmissionStatus.REJECTED: ("rechazado", "PENDIENTE_CORRECCION", "AEAT_RECHAZO"),
            AeatSubmissionStatus.TECHNICAL_ERROR: ("error_tecnico", "PENDIENTE_CORRECCION", "AEAT_TECNICO"),
        }
        aeat_sif_estado, estado_verifactu, accion_auditoria = mapping[result.status]
        now_iso = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        update_payload: dict[str, Any] = {
            "aeat_sif_estado": aeat_sif_estado,
            "aeat_sif_csv": result.csv,
            "aeat_sif_codigo": result.error_code,
            "aeat_sif_descripcion": result.error_description,
            "aeat_sif_actualizado_en": now_iso,
        }
        try:
            await self._db.execute(
                self._db.table("facturas")
                .update({**update_payload, "estado_verifactu": estado_verifactu})
                .eq("id", fid)
                .eq("empresa_id", empresa_id)
            )
        except Exception:
            await self._db.execute(
                self._db.table("facturas")
                .update(update_payload)
                .eq("id", fid)
                .eq("empresa_id", empresa_id)
            )

        if accion_auditoria is not None:
            await self.registrar_evento(
                accion=accion_auditoria,
                registro_id=fid,
                empresa_id=empresa_id,
                detalles={
                    "factura_id": fid,
                    "num_factura": factura.get("num_factura") or factura.get("numero_factura"),
                    "estado_verifactu": estado_verifactu,
                    "aeat_sif_estado": aeat_sif_estado,
                    "codigo_error": result.error_code,
                    "descripcion_error": result.error_description,
                    "csv": result.csv,
                    "http_status": result.http_status,
                    "huella": payload["huella"],
                },
            )

        return {
            "factura_id": fid,
            "aeat_sif_estado": aeat_sif_estado,
            "estado_verifactu": estado_verifactu,
            "csv": result.csv,
            "codigo_error": result.error_code,
            "descripcion_error": result.error_description,
            "http_status": result.http_status,
            "huella": payload["huella"],
        }

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

