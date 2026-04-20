from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.esg_audit import (
    CertificacionEmisiones,
    ESGAuditCertificacionPie,
    ESGAuditClienteItem,
    ESGAuditOut,
)

# Diferencia teórica de eficiencia Euro V → Euro VI (escenario de negocio).
EUROVI_VS_EUROV_EFICIENCIA_RELATIVA = 0.15
# Porcentaje de portes Euro V considerados en el escenario de optimización (por defecto).
DEFAULT_ESCENARIO_OPTIMIZACION_PCT = 25.0

VALID_CERTS: frozenset[str] = frozenset({"Euro V", "Euro VI", "Electrico", "Hibrido"})

# Solo certificados emitidos en flujo Enterprise ``pending_external_audit`` (QR Due Diligence).
_PRE_EXTERNALLY_VERIFIED: frozenset[str] = frozenset({"pending_external_audit"})


def esg_external_webhook_signature_hex(*, secret: str, raw_body: bytes) -> str:
    """HMAC-SHA256 (hex minúsculas) del cuerpo crudo; misma semántica que webhooks de pago."""
    key = str(secret or "").encode("utf-8")
    return hmac.new(key, raw_body, hashlib.sha256).hexdigest()


def verify_esg_external_webhook_signature(
    *, secret: str, raw_body: bytes, signature_header: str | None
) -> bool:
    """
    Cabecera esperada: ``X-ABL-ESG-Signature: <hex>`` o prefijo ``sha256=`` (compat).
    Comparación en tiempo constante.
    """
    want = esg_external_webhook_signature_hex(secret=secret, raw_body=raw_body)
    raw = (signature_header or "").strip()
    if raw.lower().startswith("sha256="):
        raw = raw.split("=", 1)[1].strip()
    got = raw.lower()
    if len(got) != 64:
        return False
    return hmac.compare_digest(want, got)

# Origen canónico del enlace QR (Due Diligence); sobreescribible con ``ESG_VERIFY_API_ORIGIN``.
_DEFAULT_ESG_VERIFY_API_ORIGIN = "https://api.ablogistics.io"


def certificate_content_sha256_hex(pdf_bytes: bytes) -> str:
    """
    SHA-256 hexadecimal del binario PDF del certificado (integridad frente a manipulación).
    Debe coincidir con ``certificate_content_sha256`` / ``sha256_pdf`` en ``esg_certificate_documents``.
    """
    return hashlib.sha256(pdf_bytes).hexdigest()


def public_esg_verify_url(*, api_origin: str | None, verification_code: str) -> str:
    """
    URL absoluta escaneable en QR: ``{origin}/v1/public/verify-esg/{verification_code}``.
    """
    base = (api_origin or _DEFAULT_ESG_VERIFY_API_ORIGIN).strip().rstrip("/")
    code = str(verification_code).strip()
    return f"{base}/v1/public/verify-esg/{code}"


def _norm_cert(raw: str | None) -> CertificacionEmisiones:
    s = (raw or "").strip()
    if s in VALID_CERTS:
        return s  # type: ignore[return-value]
    return "Euro VI"


def _co2_val(row: dict[str, Any]) -> float:
    v = row.get("co2_emitido")
    if v is None:
        return 0.0
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


class EsgAuditService:
    """Auditoría ESG (huella por portes facturados y certificación de flota)."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def audit_report(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        escenario_pct: float = DEFAULT_ESCENARIO_OPTIMIZACION_PCT,
    ) -> ESGAuditOut:
        eid = str(empresa_id or "").strip()
        if not eid:
            return ESGAuditOut(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                total_huella_carbono_kg=0.0,
                top_clientes=[],
                porcentaje_emisiones_euro_v=0.0,
                porcentaje_emisiones_euro_vi=0.0,
                desglose_certificacion=[],
                insight_optimizacion="Sin datos de período.",
                escenario_optimizacion_pct=min(100.0, max(0.0, escenario_pct)),
                co2_ahorro_escenario_kg=0.0,
            )

        fi = fecha_inicio.isoformat()
        ff = fecha_fin.isoformat()

        try:
            qp = filter_not_deleted(
                self._db.table("portes")
                .select("id,cliente_id,vehiculo_id,co2_emitido,fecha")
                .eq("empresa_id", eid)
                .eq("estado", "facturado")
                .gte("fecha", fi)
                .lte("fecha", ff)
            )
            rp: Any = await self._db.execute(qp)
            porte_rows: list[dict[str, Any]] = (rp.data or []) if hasattr(rp, "data") else []
        except Exception:
            porte_rows = []

        veh_ids: set[str] = set()
        for r in porte_rows:
            vid = r.get("vehiculo_id")
            if vid is not None:
                veh_ids.add(str(vid))

        flota_cert: dict[str, str] = {}
        veh_cert: dict[str, str] = {}
        if veh_ids:
            ids_list = list(veh_ids)
            try:
                rf = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("flota")
                        .select("id,certificacion_emisiones")
                        .eq("empresa_id", eid)
                        .in_("id", ids_list)
                    )
                )
                for row in (rf.data or []) if hasattr(rf, "data") else []:
                    i = row.get("id")
                    if i is not None:
                        flota_cert[str(i)] = str(row.get("certificacion_emisiones") or "Euro VI")
            except Exception:
                pass
            try:
                rv = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("vehiculos")
                        .select("id,certificacion_emisiones")
                        .eq("empresa_id", eid)
                        .in_("id", ids_list)
                    )
                )
                for row in (rv.data or []) if hasattr(rv, "data") else []:
                    i = row.get("id")
                    if i is not None:
                        veh_cert[str(i)] = str(row.get("certificacion_emisiones") or "Euro VI")
            except Exception:
                pass

        def cert_for_vehiculo(vid: str | None) -> CertificacionEmisiones:
            if not vid:
                return "Euro VI"
            s = str(vid).strip()
            c = flota_cert.get(s) or veh_cert.get(s)
            return _norm_cert(c)

        co2_by_cliente: dict[str, float] = defaultdict(float)
        co2_by_cert: dict[str, float] = defaultdict(float)
        co2_euro_v = 0.0
        total_co2 = 0.0

        for r in porte_rows:
            c2 = _co2_val(r)
            total_co2 += c2
            cid = r.get("cliente_id")
            if cid is not None:
                cs = str(cid)
                co2_by_cliente[cs] += c2
            cert = cert_for_vehiculo(r.get("vehiculo_id"))
            co2_by_cert[cert] += c2
            if cert == "Euro V":
                co2_euro_v += c2

        pct_total = total_co2 if total_co2 > 0 else 1.0
        pct_euro_v = (co2_by_cert["Euro V"] / pct_total) * 100.0
        pct_euro_vi = (co2_by_cert["Euro VI"] / pct_total) * 100.0

        pie: list[ESGAuditCertificacionPie] = []
        for cert in ("Euro V", "Euro VI", "Electrico", "Hibrido"):
            kg = co2_by_cert.get(cert, 0.0)
            pie.append(
                ESGAuditCertificacionPie(
                    certificacion=cert,  # type: ignore[arg-type]
                    co2_kg=kg,
                    porcentaje=(kg / pct_total) * 100.0,
                )
            )

        top_sorted = sorted(co2_by_cliente.items(), key=lambda x: x[1], reverse=True)[:5]
        top_ids = [k for k, _ in top_sorted]

        nombres: dict[str, str] = {}
        if top_ids:
            try:
                rc = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes")
                        .select("id,nombre_comercial,nombre")
                        .eq("empresa_id", eid)
                        .in_("id", top_ids)
                    )
                )
                for row in (rc.data or []) if hasattr(rc, "data") else []:
                    i = row.get("id")
                    if i is None:
                        continue
                    nc = row.get("nombre_comercial")
                    nm = row.get("nombre")
                    label = ""
                    if nc and str(nc).strip():
                        label = str(nc).strip()
                    elif nm and str(nm).strip():
                        label = str(nm).strip()
                    nombres[str(i)] = label if label else None
            except Exception:
                pass

        top_clientes: list[ESGAuditClienteItem] = []
        for cid, kg in top_sorted:
            top_clientes.append(
                ESGAuditClienteItem(
                    cliente_id=UUID(cid),
                    cliente_nombre=nombres.get(cid),
                    co2_kg=kg,
                )
            )

        # Escenario: fracción de portes Euro V × CO2 Euro V × 15% eficiencia.
        scen = min(100.0, max(0.0, float(escenario_pct)))
        co2_ahorro = co2_euro_v * (scen / 100.0) * EUROVI_VS_EUROV_EFICIENCIA_RELATIVA

        if co2_euro_v <= 0:
            insight = (
                "No hay portes facturados con flota Euro V en el período; "
                "no aplica estimación de ahorro por upgrade a Euro VI."
            )
        else:
            insight = (
                f"Si el {scen:.0f}% de los portes realizados con Euro V se hubieran hecho con Euro VI, "
                f"habrías ahorrado {co2_ahorro:.2f} kg de CO₂ (supuesto {int(EUROVI_VS_EUROV_EFICIENCIA_RELATIVA * 100)}% "
                "de eficiencia adicional entre normas)."
            )

        return ESGAuditOut(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            total_huella_carbono_kg=total_co2,
            top_clientes=top_clientes,
            porcentaje_emisiones_euro_v=round(pct_euro_v, 2),
            porcentaje_emisiones_euro_vi=round(pct_euro_vi, 2),
            desglose_certificacion=pie,
            insight_optimizacion=insight,
            escenario_optimizacion_pct=scen,
            co2_ahorro_escenario_kg=round(co2_ahorro, 4),
        )

    async def mark_certificate_externally_verified(
        self,
        *,
        verification_code: str,
    ) -> dict[str, Any]:
        """
        Transición a ``externally_verified`` en ``esg_certificate_documents``.

        Invocable solo tras autorización explícita (rol admin o webhook firmado).
        Idempotente si ya estaba verificado externamente.
        """
        code = str(verification_code or "").strip()
        if len(code) < 8:
            raise ValueError("verification_code inválido")

        try:
            res: Any = await self._db.execute(
                self._db.table("esg_certificate_documents")
                .select("id,empresa_id,certificate_id,verification_status,verification_code")
                .eq("verification_code", code)
                .limit(1)
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            raise ValueError("No se pudo consultar el certificado") from exc

        if not rows:
            raise ValueError("Certificado no encontrado")

        row = rows[0]
        prev = str(row.get("verification_status") or "").strip()
        if prev == "externally_verified":
            return {
                "updated": False,
                "verification_code": code,
                "verification_status": "externally_verified",
                "previous_status": prev,
                "certificate_id": str(row.get("certificate_id") or "") or None,
                "empresa_id": str(row.get("empresa_id") or "") or None,
            }

        if prev not in _PRE_EXTERNALLY_VERIFIED:
            raise ValueError(
                f"Estado actual ({prev!r}) no admite transición a externally_verified"
            )

        row_id = row.get("id")
        try:
            await self._db.execute(
                self._db.table("esg_certificate_documents")
                .update({"verification_status": "externally_verified"})
                .eq("id", row_id)
            )
        except Exception as exc:
            raise ValueError("No se pudo actualizar el estado del certificado") from exc

        return {
            "updated": True,
            "verification_code": code,
            "verification_status": "externally_verified",
            "previous_status": prev,
            "certificate_id": str(row.get("certificate_id") or "") or None,
            "empresa_id": str(row.get("empresa_id") or "") or None,
        }
