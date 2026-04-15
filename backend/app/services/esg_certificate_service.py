"""
Certificados ESG emitidos solo en servidor: GLEC (``esg_engine``) + huella PDF + registro auditable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.crypto import pii_crypto
from app.core.esg_engine import (
    calculate_nox_emissions,
    esg_certificate_co2_vs_euro_iii,
    glec_emission_factors_gco2_per_km,
)
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.facturas_service import FacturasService
from app.services.pdf_esg_service import (
    EsgFacturaCertificatePdfModel,
    EsgPorteCertificatePdfModel,
    generar_pdf_certificado_esg_factura_glec,
    generar_pdf_certificado_esg_porte_glec,
)
from app.services.portes_service import PortesService

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


async def _empresa_nombre_y_nif(db: SupabaseAsync, empresa_id: str) -> tuple[str, str]:
    nombre = "Empresa"
    nif = ""
    try:
        res: Any = await db.execute(
            db.table("empresas").select("nombre_comercial,nombre_legal,nif").eq("id", empresa_id).limit(1)
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
    except Exception:
        pass
    return nombre, nif


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
    ) -> bytes:
        eid = str(empresa_id).strip()
        pid = str(porte_id).strip()
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

        nombre_em, nif_em = await _empresa_nombre_y_nif(self._db, eid)
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
        )

        pdf_bytes = generar_pdf_certificado_esg_porte_glec(model)
        sha_pdf = hashlib.sha256(pdf_bytes).hexdigest()

        try:
            await self._persist_audit_row(
                empresa_id=eid,
                certificate_id=cert_id,
                subject_type="porte",
                subject_id=pid,
                sha256_pdf=sha_pdf,
                content_fingerprint_sha256=fp,
                metadata={
                    "porte_id": pid,
                    "sha256_pdf": sha_pdf,
                    "methodology": "GLEC v2.0 / ISO 14083 (platform implementation)",
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
    ) -> bytes:
        eid = str(empresa_id).strip()
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
        )

        pdf_bytes = generar_pdf_certificado_esg_factura_glec(model)
        sha_pdf = hashlib.sha256(pdf_bytes).hexdigest()

        try:
            await self._persist_audit_row(
                empresa_id=eid,
                certificate_id=cert_id,
                subject_type="factura",
                subject_id=str(factura_id),
                sha256_pdf=sha_pdf,
                content_fingerprint_sha256=fp,
                metadata={
                    "factura_id": factura_id,
                    "sha256_pdf": sha_pdf,
                    "methodology": "GLEC v2.0 / ISO 14083 (aggregated per porte)",
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
