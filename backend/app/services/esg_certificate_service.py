"""
Certificados ESG emitidos solo en servidor: GLEC (``esg_engine``) + huella PDF + registro auditable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE, ISO_14083_REFERENCE_LABEL
from app.core.crypto import pii_crypto
from app.core.i18n import normalize_lang
from app.core.plans import PLAN_ENTERPRISE, fetch_empresa_plan, normalize_plan
from app.core.esg_engine import (
    calculate_nox_emissions,
    esg_certificate_co2_vs_euro_iii,
    glec_emission_factors_gco2_per_km,
)
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.facturas_service import FacturasService
from app.services.esg_service import generate_porte_certificate_pdf_reportlab
from app.services.pdf_esg_service import (
    EsgFacturaCertificatePdfModel,
    EsgPorteCertificatePdfModel,
    generar_pdf_certificado_esg_factura_glec,
)
from app.services.portes_service import PortesService
from app.schemas.esg_verify import EsgPublicVerifyEmissions, EsgPublicVerifyOut
from app.services.esg_audit_service import (
    certificate_content_sha256_hex,
    public_esg_verify_url,
)

_log = logging.getLogger(__name__)


def _new_certificate_id() -> str:
    return f"ABL-ESG-{date.today().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


def _content_fingerprint_sha256(
    *,
    certificate_id: str,
    empresa_id: str,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
) -> str:
    blob = json.dumps(
        {
            "certificate_id": certificate_id,
            "empresa_id": empresa_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def _empresa_nombre_nif_lang(db: SupabaseAsync, empresa_id: str) -> tuple[str, str, str]:
    nombre = "Empresa"
    nif = ""
    lang = "es"
    try:
        res: Any = await db.execute(
            db.table("empresas")
            .select("nombre_comercial,nombre_legal,nif,preferred_language")
            .eq("id", empresa_id)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if rows:
            r = rows[0]
            nombre = (
                str(r.get("nombre_comercial") or "").strip()
                or str(r.get("nombre_legal") or "").strip()
                or nombre
            )
            raw_nif = str(r.get("nif") or "").strip()
            nif = (pii_crypto.decrypt_pii(raw_nif) or raw_nif).strip()
            lang = normalize_lang(str(r.get("preferred_language") or "es"))
    except Exception:
        pass
    return nombre, nif, lang


class EsgCertificateService:
    def __init__(
        self,
        db: SupabaseAsync,
        portes: PortesService,
        facturas: FacturasService,
    ) -> None:
        self._db = db
        self._portes = portes
        self._facturas = facturas

    async def _persist_audit_row(
        self,
        *,
        empresa_id: str,
        certificate_id: str,
        subject_type: str,
        subject_id: str,
        sha256_pdf: str,
        content_fingerprint_sha256: str,
        certificate_content_sha256: str,
        verification_code: str,
        verification_status: str,
        metadata: dict[str, Any],
        created_by: str | None,
    ) -> None:
        row = {
            "empresa_id": empresa_id,
            "certificate_id": certificate_id,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "sha256_pdf": sha256_pdf,
            "content_fingerprint_sha256": content_fingerprint_sha256,
            "certificate_content_sha256": certificate_content_sha256,
            "verification_code": verification_code,
            "verification_status": verification_status,
            "metadata": metadata,
            "created_by": created_by,
        }
        await self._db.execute(self._db.table("esg_certificate_documents").insert(row))

    async def generate_porte_certificate_pdf(
        self,
        *,
        empresa_id: str,
        porte_id: str,
        usuario_id: str | None,
        official_audit: bool = False,
    ) -> bytes:
        eid = str(empresa_id).strip()
        pid = str(porte_id).strip()
        if official_audit:
            plan = await fetch_empresa_plan(self._db, empresa_id=eid)
            if normalize_plan(plan) != PLAN_ENTERPRISE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="La validación oficial requiere plan Enterprise (Tier Full-Stack).",
                )
        verification_status = (
            "pending_external_audit" if official_audit else "self_certified"
        )
        verification_code = str(uuid4())
        verify_url = public_esg_verify_url(
            api_origin=get_settings().ESG_VERIFY_API_ORIGIN,
            verification_code=verification_code,
        )

        porte = await self._portes.get_porte(empresa_id=eid, porte_id=pid)
        if porte is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Porte no encontrado")

        km_reales: float | None = None
        real_distance_km: float | None = None
        try:
            res_p: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("portes")
                    .select("km_reales, real_distance_meters")
                    .eq("empresa_id", eid)
                    .eq("id", pid)
                    .limit(1)
                )
            )
            pr = (res_p.data or []) if hasattr(res_p, "data") else []
            if pr:
                raw_km = pr[0].get("km_reales")
                if raw_km is not None:
                    km_reales = max(0.0, float(raw_km))
                raw_m = pr[0].get("real_distance_meters")
                if raw_m is not None:
                    try:
                        rm = float(raw_m)
                        if rm > 0:
                            real_distance_km = round(rm / 1000.0, 6)
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass

        cert_id = _new_certificate_id()
        ec = porte.vehiculo_engine_class
        ft = porte.vehiculo_fuel_type
        g_full, g_empty = glec_emission_factors_gco2_per_km(engine_class=ec, fuel_type=ft)

        cert_vals = esg_certificate_co2_vs_euro_iii(
            km_estimados=float(porte.km_estimados or 0.0),
            km_vacio=porte.km_vacio,
            engine_class=ec,
            fuel_type=ft,
            subcontratado=bool(porte.subcontratado),
        )
        co2_total = float(cert_vals["actual_total_kg"])
        euro_iii = float(cert_vals["euro_iii_baseline_kg"])
        ahorro = float(cert_vals["ahorro_kg"])

        norma = str(porte.vehiculo_normativa_euro or "Euro VI")
        nox_kg = calculate_nox_emissions(float(porte.km_estimados or 0.0), norma)

        mat = str(porte.vehiculo_matricula or "").strip()
        mod = str(porte.vehiculo_modelo or "").strip()
        veh_label = " · ".join(x for x in (mat, mod) if x) or "—"

        nombre_em, nif_em, pdf_lang = await _empresa_nombre_nif_lang(self._db, eid)
        fecha_str = str(porte.fecha)[:10] if porte.fecha else "—"

        payload = {
            "co2_total_kg": round(co2_total, 6),
            "euro_iii_baseline_kg": round(euro_iii, 6),
            "ahorro_kg": round(ahorro, 6),
            "km_estimados": float(porte.km_estimados or 0.0),
            "nox_kg": round(nox_kg, 6),
            "subcontratado": bool(porte.subcontratado),
        }
        fp = _content_fingerprint_sha256(
            certificate_id=cert_id,
            empresa_id=eid,
            subject_type="porte",
            subject_id=pid,
            payload=payload,
        )

        scope_note = (
            "Emisiones contabilizadas como Scope 3 (transporte subcontratado)."
            if porte.subcontratado
            else "Emisiones operativas Scope 1 cuando aplica combustible de flota propia."
        )

        model = EsgPorteCertificatePdfModel(
            certificate_id=cert_id,
            content_fingerprint_sha256=fp,
            empresa_nombre=nombre_em,
            empresa_nif=nif_em,
            porte_id=pid,
            fecha=fecha_str,
            origen=str(porte.origen),
            destino=str(porte.destino),
            km_estimados=float(porte.km_estimados or 0.0),
            km_reales=km_reales,
            real_distance_km=real_distance_km,
            km_vacio=float(porte.km_vacio) if porte.km_vacio is not None else None,
            engine_class=ec,
            fuel_type=ft,
            vehiculo_label=veh_label,
            normativa_euro=norma,
            glec_gco2_km_full=g_full,
            glec_gco2_km_empty=g_empty,
            co2_total_kg=co2_total,
            euro_iii_baseline_kg=euro_iii,
            ahorro_kg=ahorro,
            nox_total_kg=nox_kg,
            subcontratado=bool(porte.subcontratado),
            scope_note=scope_note,
            verify_url=verify_url,
        )

        pdf_bytes = generate_porte_certificate_pdf_reportlab(model, lang=pdf_lang)
        sha_pdf = certificate_content_sha256_hex(pdf_bytes)

        try:
            await self._persist_audit_row(
                empresa_id=eid,
                certificate_id=cert_id,
                subject_type="porte",
                subject_id=pid,
                sha256_pdf=sha_pdf,
                content_fingerprint_sha256=fp,
                certificate_content_sha256=sha_pdf,
                verification_code=verification_code,
                verification_status=verification_status,
                metadata={
                    "porte_id": pid,
                    "sha256_pdf": sha_pdf,
                    "verification_code": verification_code,
                    "verification_status": verification_status,
                    "methodology": "GLEC v2.0 + ISO 14083 diesel 2,67 kg/L (ReportLab certificate)",
                    "emissions": {
                        "subject": "porte",
                        "co2_total_kg": round(co2_total, 6),
                        "euro_iii_baseline_kg": round(euro_iii, 6),
                        "ahorro_vs_euro_iii_kg": round(ahorro, 6),
                    },
                },
                created_by=usuario_id,
            )
        except Exception as exc:
            _log.exception("Fallo al registrar certificado ESG en base de datos: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo completar el registro de auditoría del certificado.",
            ) from exc

        return pdf_bytes

    async def generate_factura_certificate_pdf(
        self,
        *,
        empresa_id: str,
        factura_id: int,
        usuario_id: str | None,
        official_audit: bool = False,
    ) -> bytes:
        eid = str(empresa_id).strip()
        if official_audit:
            plan = await fetch_empresa_plan(self._db, empresa_id=eid)
            if normalize_plan(plan) != PLAN_ENTERPRISE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="La validación oficial requiere plan Enterprise (Tier Full-Stack).",
                )
        verification_status = (
            "pending_external_audit" if official_audit else "self_certified"
        )
        verification_code = str(uuid4())
        verify_url = public_esg_verify_url(
            api_origin=get_settings().ESG_VERIFY_API_ORIGIN,
            verification_code=verification_code,
        )

        try:
            pdf_data = await self._facturas.get_factura_pdf_data(empresa_id=eid, factura_id=factura_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        if (
            pdf_data.esg_total_co2_kg is None
            or pdf_data.esg_euro_iii_baseline_kg is None
            or pdf_data.esg_total_km is None
            or pdf_data.esg_portes_count is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La factura no tiene agregado ESG (sin portes vinculados o datos incompletos).",
            )

        cert_id = _new_certificate_id()
        co2 = float(pdf_data.esg_total_co2_kg)
        base = float(pdf_data.esg_euro_iii_baseline_kg)
        ahorro = float(pdf_data.esg_ahorro_vs_euro_iii_kg) if pdf_data.esg_ahorro_vs_euro_iii_kg is not None else max(0.0, base - co2)

        payload = {
            "esg_total_co2_kg": round(co2, 6),
            "esg_euro_iii_baseline_kg": round(base, 6),
            "esg_ahorro_kg": round(ahorro, 6),
            "esg_total_km": float(pdf_data.esg_total_km),
            "esg_portes_count": int(pdf_data.esg_portes_count),
        }
        fp = _content_fingerprint_sha256(
            certificate_id=cert_id,
            empresa_id=eid,
            subject_type="factura",
            subject_id=str(factura_id),
            payload=payload,
        )

        nombre_em = pdf_data.emisor.nombre
        nif_em = (pdf_data.emisor.nif or "").strip()
        pdf_lang = pdf_data.content_language

        model = EsgFacturaCertificatePdfModel(
            certificate_id=cert_id,
            content_fingerprint_sha256=fp,
            empresa_nombre=nombre_em,
            empresa_nif=nif_em,
            factura_id=factura_id,
            numero_factura=str(pdf_data.numero_factura),
            fecha_emision=str(pdf_data.fecha_emision)[:10],
            cliente_nombre=str(pdf_data.receptor.nombre),
            esg_portes_count=int(pdf_data.esg_portes_count),
            esg_total_km=float(pdf_data.esg_total_km),
            esg_total_co2_kg=co2,
            esg_euro_iii_baseline_kg=base,
            esg_ahorro_kg=ahorro,
            verify_url=verify_url,
        )

        pdf_bytes = generar_pdf_certificado_esg_factura_glec(model, lang=pdf_lang)
        sha_pdf = certificate_content_sha256_hex(pdf_bytes)

        try:
            await self._persist_audit_row(
                empresa_id=eid,
                certificate_id=cert_id,
                subject_type="factura",
                subject_id=str(factura_id),
                sha256_pdf=sha_pdf,
                content_fingerprint_sha256=fp,
                certificate_content_sha256=sha_pdf,
                verification_code=verification_code,
                verification_status=verification_status,
                metadata={
                    "factura_id": factura_id,
                    "sha256_pdf": sha_pdf,
                    "verification_code": verification_code,
                    "verification_status": verification_status,
                    "methodology": "GLEC v2.0 / ISO 14083 (aggregated per porte)",
                    "emissions": {
                        "subject": "factura",
                        "co2_total_kg": round(co2, 6),
                        "euro_iii_baseline_kg": round(base, 6),
                        "ahorro_vs_euro_iii_kg": round(ahorro, 6),
                        "esg_total_km": float(pdf_data.esg_total_km),
                        "esg_portes_count": int(pdf_data.esg_portes_count),
                    },
                },
                created_by=usuario_id,
            )
        except Exception as exc:
            _log.exception("Fallo al registrar certificado ESG en base de datos: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo completar el registro de auditoría del certificado.",
            ) from exc

        return pdf_bytes


def parse_subject_uuid(subject_id: str) -> UUID:
    try:
        return UUID(str(subject_id).strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identificador de porte inválido (se espera UUID).",
        ) from exc


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


async def fetch_esg_verification_public(
    db: SupabaseAsync,
    *,
    verification_code: str,
    pdf_sha256: str | None,
) -> EsgPublicVerifyOut:
    """Lectura por ``verification_code`` (cliente service role / bypass RLS)."""
    raw = str(verification_code or "").strip()
    if len(raw) < 8:
        return EsgPublicVerifyOut(
            valid=False,
            found=False,
            methodology_note=ISO_14083_REFERENCE_LABEL,
        )

    try:
        res: Any = await db.execute(
            db.table("esg_certificate_documents")
            .select(
                "certificate_id,verification_status,subject_type,subject_id,"
                "certificate_content_sha256,content_fingerprint_sha256,metadata,created_at"
            )
            .eq("verification_code", raw)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        rows = []

    if not rows:
        return EsgPublicVerifyOut(
            valid=False,
            found=False,
            methodology_note=ISO_14083_REFERENCE_LABEL,
        )

    row = rows[0]
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    em_raw = meta.get("emissions") if isinstance(meta.get("emissions"), dict) else {}

    emissions = EsgPublicVerifyEmissions(
        co2_total_kg=_float_or_none(em_raw.get("co2_total_kg")),
        euro_iii_baseline_kg=_float_or_none(em_raw.get("euro_iii_baseline_kg")),
        ahorro_vs_euro_iii_kg=_float_or_none(em_raw.get("ahorro_vs_euro_iii_kg")),
        esg_total_km=_float_or_none(em_raw.get("esg_total_km")),
        esg_portes_count=(
            int(em_raw["esg_portes_count"])
            if em_raw.get("esg_portes_count") is not None
            and str(em_raw.get("esg_portes_count")).strip() != ""
            else None
        ),
        iso_14083_diesel_kg_co2eq_per_litre=ISO_14083_DIESEL_CO2_KG_PER_LITRE,
    )

    reg_hash = str(row.get("certificate_content_sha256") or "").strip().lower()
    want = (pdf_sha256 or "").strip().lower() if pdf_sha256 else ""
    pdf_match: bool | None = None
    if pdf_sha256 is not None and str(pdf_sha256).strip():
        pdf_match = bool(reg_hash) and reg_hash == want

    valid = True
    if pdf_match is False:
        valid = False

    return EsgPublicVerifyOut(
        valid=valid,
        found=True,
        certificate_id=str(row.get("certificate_id") or "") or None,
        verification_status=str(row.get("verification_status") or "") or None,
        subject_type=str(row.get("subject_type") or "") or None,
        subject_id=None,
        certificate_content_sha256=str(row.get("certificate_content_sha256") or "") or None,
        content_fingerprint_sha256=str(row.get("content_fingerprint_sha256") or "") or None,
        pdf_sha256_matches=pdf_match,
        issued_at=_parse_created_at(row.get("created_at")),
        emissions=emissions,
        methodology_note=ISO_14083_REFERENCE_LABEL,
    )
