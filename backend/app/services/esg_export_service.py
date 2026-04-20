"""
Exportación auditor-ready de emisiones (ISO 14083) sin PII.

Solo columnas agregadas por línea de cálculo: Fecha, Euro_Class, Km, Litros, Kg_CO2.
No se exponen origen/destino, conductor, matrícula ni IDs de porte en el CSV/JSON de líneas.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Any

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE, ISO_14083_REFERENCE_LABEL
from app.core.esg_engine import calculate_co2_emissions, resolve_normativa_euro_for_co2
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.esg_audit_service import _norm_cert


def _co2_kg(row: dict[str, Any], *, km: float, euro_label: str) -> float:
    v = row.get("co2_emitido")
    if v is None:
        return max(0.0, float(calculate_co2_emissions(km, euro_label)))
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return max(0.0, float(calculate_co2_emissions(km, euro_label)))


def _km_operativo(row: dict[str, Any]) -> float:
    kr = row.get("km_reales")
    ke = row.get("km_estimados")
    try:
        if kr is not None and float(kr) > 0:
            return max(0.0, float(kr))
    except (TypeError, ValueError):
        pass
    try:
        return max(0.0, float(ke or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _litros_implied_diesel_iso14083(*, kg_co2: float) -> float:
    """Litros equivalentes diésel vía factor ISO 14083 (coherencia certificados / auditoría)."""
    if kg_co2 <= 0 or ISO_14083_DIESEL_CO2_KG_PER_LITRE <= 0:
        return 0.0
    return round(kg_co2 / float(ISO_14083_DIESEL_CO2_KG_PER_LITRE), 6)


class EsgExportService:
    """Paquete JSON/CSV importable en Excel o Pandas (coma + UTF-8 BOM en CSV)."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def build_masked_emissions_rows(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        redact_workspace: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        eid = str(empresa_id or "").strip()
        meta: dict[str, Any] = {
            "empresa_id": eid,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "iso_14083_diesel_kg_co2eq_per_litre": ISO_14083_DIESEL_CO2_KG_PER_LITRE,
            "iso_14083_reference": ISO_14083_REFERENCE_LABEL,
            "pii_policy": "no_route_no_driver_no_plate_no_ids_in_row_payload",
            "csv_columns": ["Fecha", "Euro_Class", "Km", "Litros", "Kg_CO2"],
        }
        if redact_workspace:
            meta.pop("empresa_id", None)
            meta["tenant_scope"] = "redacted_for_external_auditor"
        if not eid:
            meta["row_count"] = 0
            return [], meta

        fi = fecha_inicio.isoformat()
        ff = fecha_fin.isoformat()

        try:
            qp = filter_not_deleted(
                self._db.table("portes")
                .select("id,vehiculo_id,km_estimados,km_reales,co2_emitido,fecha,estado")
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
        flota_norm: dict[str, str] = {}
        veh_cert: dict[str, str] = {}
        if veh_ids:
            ids_list = list(veh_ids)
            try:
                rf = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("flota")
                        .select("id,certificacion_emisiones,normativa_euro")
                        .eq("empresa_id", eid)
                        .in_("id", ids_list)
                    )
                )
                for row in (rf.data or []) if hasattr(rf, "data") else []:
                    i = row.get("id")
                    if i is not None:
                        sid = str(i)
                        flota_cert[sid] = str(row.get("certificacion_emisiones") or "Euro VI")
                        ne = row.get("normativa_euro")
                        if ne is not None and str(ne).strip():
                            flota_norm[sid] = str(ne).strip()
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

        def euro_for_porte(vid: str | None) -> str:
            if not vid:
                return resolve_normativa_euro_for_co2(
                    normativa_euro=None,
                    certificacion_emisiones="Euro VI",
                )
            s = str(vid).strip()
            raw_cert = flota_cert.get(s) or veh_cert.get(s)
            norm = flota_norm.get(s)
            cert_label = _norm_cert(raw_cert)
            return resolve_normativa_euro_for_co2(
                normativa_euro=norm,
                certificacion_emisiones=cert_label,
            )

        out_rows: list[dict[str, Any]] = []
        for r in porte_rows:
            raw_fecha = r.get("fecha")
            if raw_fecha is None:
                continue
            fecha_s = str(raw_fecha)[:10]
            km = _km_operativo(r)
            euro = euro_for_porte(r.get("vehiculo_id"))
            kg = _co2_kg(r, km=km, euro_label=euro)
            litros = _litros_implied_diesel_iso14083(kg_co2=kg)
            out_rows.append(
                {
                    "Fecha": fecha_s,
                    "Euro_Class": euro,
                    "Km": round(km, 6),
                    "Litros": litros,
                    "Kg_CO2": round(kg, 6),
                }
            )

        meta["row_count"] = len(out_rows)
        return out_rows, meta

    async def export_json_bytes(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        redact_workspace: bool = False,
    ) -> bytes:
        rows, meta = await self.build_masked_emissions_rows(
            empresa_id=empresa_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            redact_workspace=redact_workspace,
        )
        payload = {"meta": meta, "rows": rows}
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    async def export_csv_bytes(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> bytes:
        rows, _meta = await self.build_masked_emissions_rows(
            empresa_id=empresa_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        buf = io.StringIO()
        buf.write("\ufeff")
        w = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(["Fecha", "Euro_Class", "Km", "Litros", "Kg_CO2"])
        for r in rows:
            w.writerow(
                [
                    r["Fecha"],
                    r["Euro_Class"],
                    r["Km"],
                    r["Litros"],
                    r["Kg_CO2"],
                ]
            )
        return buf.getvalue().encode("utf-8")
