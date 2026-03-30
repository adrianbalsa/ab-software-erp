from __future__ import annotations

import calendar
import csv
from collections import defaultdict
from datetime import date, datetime
import os
from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.esg import (
    EsgAuditReadyOut,
    EsgAuditReadyRow,
    HuellaCarbonoMensualOut,
    VehiculoHuellaMesOut,
)
from app.core.esg_engine import (
    calculate_co2_emissions,
    calculate_nox_emissions,
    get_co2_factor_kg_per_km,
)
from app.services.eco_service import (
    factor_emision_huella_porte_default,
    peso_ton_desde_porte_row,
)
from app.services.maps_service import MapsService


def _tipo_motor_a_factor(tipo: str | None) -> float:
    """Factor kg CO₂ / (t·km) por tipo de motor si no hay factor en flota."""
    base = factor_emision_huella_porte_default()
    t = (tipo or "").strip().lower()
    if "eléctrico" in t or "electrico" in t:
        return 0.012
    if "híbrido" in t:
        return base * 0.55
    if "gasolina" in t:
        return base * 1.12
    return base


def _factor_desde_flota_row(row: dict[str, Any] | None) -> float:
    if row is None:
        return factor_emision_huella_porte_default()
    raw = row.get("factor_emision_co2_tkm")
    if raw is not None:
        try:
            v = float(raw)
            if v >= 0:
                return v
        except (TypeError, ValueError):
            pass
    return _tipo_motor_a_factor(str(row.get("tipo_motor")))


class EsgService:
    """
    Huella de carbono operativa (portes facturados) con km de ruta (Google / caché)
    y factor por vehículo (perfil flota).
    """

    def __init__(self, db: SupabaseAsync, maps: MapsService) -> None:
        self._db = db
        self._maps = maps

    async def nombre_empresa_publico(self, *, empresa_id: str) -> str:
        eid = str(empresa_id or "").strip()
        if not eid:
            return "Empresa"
        try:
            res: Any = await self._db.execute(
                self._db.table("empresas")
                .select("nombre_comercial,nombre_legal")
                .eq("id", eid)
                .limit(1)
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            return f"Empresa ({eid[:8]}…)"
        if not rows:
            return f"Empresa ({eid[:8]}…)"
        r = rows[0]
        nc = r.get("nombre_comercial")
        if nc and str(nc).strip():
            return str(nc).strip()
        nl = r.get("nombre_legal")
        if nl and str(nl).strip():
            return str(nl).strip()
        return f"Empresa ({eid[:8]}…)"

    async def _cargar_flota_por_ids(
        self, *, empresa_id: str, ids: set[str]
    ) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        eid = str(empresa_id or "").strip()
        try:
            res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select(
                        "id, matricula, vehiculo, tipo_motor, factor_emision_co2_tkm, normativa_euro"
                    )
                    .eq("empresa_id", eid)
                    .in_("id", list(ids))
                )
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            rid = r.get("id")
            if rid is not None:
                out[str(rid)] = dict(r)
        return out

    async def calcular_huella_carbono_mensual(
        self,
        *,
        empresa_id: str,
        mes: int,
        anio: int,
    ) -> HuellaCarbonoMensualOut:
        """
        Suma km reales (Distance Matrix con caché) × toneladas × factor del vehículo
        para portes **facturados** en el mes calendario indicado.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return HuellaCarbonoMensualOut(
                empresa_id="",
                anio=anio,
                mes=mes,
                total_co2_kg=0.0,
                total_km_reales=0.0,
                num_portes_facturados=0,
                media_co2_por_porte_kg=0.0,
                ahorro_estimado_rutas_optimizadas_kg=0.0,
                por_vehiculo=[],
            )

        ultimo = calendar.monthrange(anio, mes)[1]
        fecha_ini = date(anio, mes, 1)
        fecha_fin = date(anio, mes, ultimo)

        try:
            q = filter_not_deleted(
                self._db.table("portes")
                .select(
                    "id, origen, destino, km_estimados, peso_ton, bultos, vehiculo_id, "
                    "co2_emitido, fecha"
                )
                .eq("empresa_id", eid)
                .eq("estado", "facturado")
                .gte("fecha", fecha_ini.isoformat())
                .lte("fecha", fecha_fin.isoformat())
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            rows = []

        vids: set[str] = set()
        for r in rows:
            vid = r.get("vehiculo_id")
            if vid is not None and str(vid).strip():
                vids.add(str(vid).strip())

        flota_por_id = await self._cargar_flota_por_ids(empresa_id=eid, ids=vids)

        total_co2 = 0.0
        total_km = 0.0
        co2_pesimista = 0.0
        agg: dict[str | None, dict[str, Any]] = defaultdict(
            lambda: {"co2": 0.0, "km": 0.0, "matricula": "", "etiqueta": ""}
        )

        for r in rows:
            origen = str(r.get("origen") or "").strip()
            destino = str(r.get("destino") or "").strip()
            km_real = 0.0
            try:
                km_real = float(
                    await self._maps.get_distance_km(
                        origen,
                        destino,
                        tenant_empresa_id=eid,
                    )
                )
            except Exception:
                km_real = float(r.get("km_estimados") or 0.0)

            peso = peso_ton_desde_porte_row(dict(r))
            vid_raw = r.get("vehiculo_id")
            vid_key: str | None = str(vid_raw).strip() if vid_raw is not None else None
            frow = flota_por_id.get(vid_key) if vid_key else None
            factor = _factor_desde_flota_row(frow)

            co2_p = max(0.0, km_real * peso * factor)
            co2_pess = max(0.0, km_real * 1.15 * peso * factor)

            total_co2 += co2_p
            total_km += km_real
            co2_pesimista += co2_pess

            key = vid_key
            e = agg[key]
            e["co2"] += co2_p
            e["km"] += km_real
            if frow:
                e["matricula"] = str(frow.get("matricula") or "—")
                mot = str(frow.get("tipo_motor") or "")
                nom = str(frow.get("vehiculo") or "").strip()
                e["etiqueta"] = f"{nom} ({mot})".strip() if (nom and mot) else (nom or mot or "—")
            elif vid_key:
                e["matricula"] = "FK inválida"
                e["etiqueta"] = "Factor global"
            else:
                e["matricula"] = "Sin asignar"
                e["etiqueta"] = "Factor global empresa"

        n = len(rows)
        media = total_co2 / n if n > 0 else 0.0
        ahorro = max(0.0, co2_pesimista - total_co2)

        por_v: list[VehiculoHuellaMesOut] = []
        for k, v in agg.items():
            por_v.append(
                VehiculoHuellaMesOut(
                    vehiculo_id=k,
                    matricula=str(v.get("matricula") or "—"),
                    etiqueta=str(v.get("etiqueta") or ""),
                    co2_kg=round(float(v.get("co2") or 0.0), 6),
                    km_reales=round(float(v.get("km") or 0.0), 4),
                )
            )
        por_v.sort(key=lambda x: x.co2_kg, reverse=True)

        return HuellaCarbonoMensualOut(
            empresa_id=eid,
            anio=anio,
            mes=mes,
            total_co2_kg=round(total_co2, 6),
            total_km_reales=round(total_km, 4),
            num_portes_facturados=n,
            media_co2_por_porte_kg=round(media, 6),
            ahorro_estimado_rutas_optimizadas_kg=round(ahorro, 6),
            por_vehiculo=por_v,
        )

    async def audit_ready_summary(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> EsgAuditReadyOut:
        """
        Resumen audit-ready por cliente y periodo (YYYY-MM).
        Usa `co2_emitido` si existe; si no, estima CO2/NOx según normativa EURO y km.
        """
        eid = str(empresa_id or "").strip()
        fi = fecha_inicio.isoformat()
        ff = fecha_fin.isoformat()
        if not eid:
            now = datetime.utcnow().isoformat()
            return EsgAuditReadyOut(
                empresa_id="",
                fecha_inicio=fi,
                fecha_fin=ff,
                generado_en=now,
                total_portes=0,
                total_km_estimados=0.0,
                total_co2_kg=0.0,
                total_nox_kg=0.0,
                rows=[],
            )

        try:
            q = filter_not_deleted(
                self._db.table("portes")
                .select("id, cliente_id, vehiculo_id, km_estimados, co2_emitido, fecha")
                .eq("empresa_id", eid)
                .eq("estado", "facturado")
                .gte("fecha", fi)
                .lte("fecha", ff)
            )
            res: Any = await self._db.execute(q)
            porte_rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            porte_rows = []

        vids: set[str] = set()
        cliente_ids: set[str] = set()
        for r in porte_rows:
            vid = r.get("vehiculo_id")
            if vid is not None and str(vid).strip():
                vids.add(str(vid).strip())
            cid = r.get("cliente_id")
            if cid is not None and str(cid).strip():
                cliente_ids.add(str(cid).strip())

        flota_por_id = await self._cargar_flota_por_ids(empresa_id=eid, ids=vids)

        nombres: dict[str, str] = {}
        if cliente_ids:
            try:
                rc: Any = await self._db.execute(
                    filter_not_deleted(
                        self._db.table("clientes")
                        .select("id, nombre_comercial, nombre")
                        .eq("empresa_id", eid)
                        .in_("id", list(cliente_ids))
                    )
                )
                rows = (rc.data or []) if hasattr(rc, "data") else []
                for r in rows:
                    cid = str(r.get("id") or "").strip()
                    if not cid:
                        continue
                    nc = str(r.get("nombre_comercial") or "").strip()
                    nm = str(r.get("nombre") or "").strip()
                    nombres[cid] = nc or nm or cid
            except Exception:
                pass

        def _periodo(val: Any) -> str:
            if val is None:
                return date.today().strftime("%Y-%m")
            s = str(val).strip()[:10]
            try:
                return date.fromisoformat(s).strftime("%Y-%m")
            except ValueError:
                return date.today().strftime("%Y-%m")

        agg: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "total_portes": 0,
                "total_km": 0.0,
                "total_co2": 0.0,
                "total_nox": 0.0,
            }
        )

        for r in porte_rows:
            cid = str(r.get("cliente_id") or "").strip() or "sin_cliente"
            periodo = _periodo(r.get("fecha"))
            km = float(r.get("km_estimados") or 0.0)
            co2_raw = r.get("co2_emitido")
            if co2_raw is not None:
                try:
                    co2 = max(0.0, float(co2_raw))
                except (TypeError, ValueError):
                    co2 = 0.0
            else:
                vid = str(r.get("vehiculo_id") or "").strip()
                frow = flota_por_id.get(vid)
                norma = str(frow.get("normativa_euro") or "Euro VI") if frow else "Euro VI"
                co2 = calculate_co2_emissions(km, norma)
            vid = str(r.get("vehiculo_id") or "").strip()
            frow = flota_por_id.get(vid)
            norma = str(frow.get("normativa_euro") or "Euro VI") if frow else "Euro VI"
            nox = calculate_nox_emissions(km, norma)

            key = (periodo, cid)
            agg[key]["total_portes"] += 1
            agg[key]["total_km"] += max(0.0, km)
            agg[key]["total_co2"] += co2
            agg[key]["total_nox"] += nox

        metodologia = (
            "CO2: usa co2_emitido si existe; si no, km_estimados × factor EURO (kg/km). "
            "NOx: km_estimados × factor EURO (g/km) convertido a kg."
        )

        rows_out: list[EsgAuditReadyRow] = []
        total_portes = 0
        total_km = 0.0
        total_co2 = 0.0
        total_nox = 0.0

        for (periodo, cid), v in sorted(agg.items()):
            total_portes += int(v["total_portes"])
            total_km += float(v["total_km"])
            total_co2 += float(v["total_co2"])
            total_nox += float(v["total_nox"])
            rows_out.append(
                EsgAuditReadyRow(
                    periodo=periodo,
                    cliente_id=cid,
                    cliente_nombre=nombres.get(cid),
                    total_portes=int(v["total_portes"]),
                    total_km_estimados=round(float(v["total_km"]), 3),
                    total_co2_kg=round(float(v["total_co2"]), 6),
                    total_nox_kg=round(float(v["total_nox"]), 6),
                    metodologia=metodologia,
                )
            )

        return EsgAuditReadyOut(
            empresa_id=eid,
            fecha_inicio=fi,
            fecha_fin=ff,
            generado_en=datetime.utcnow().isoformat(),
            total_portes=total_portes,
            total_km_estimados=round(total_km, 3),
            total_co2_kg=round(total_co2, 6),
            total_nox_kg=round(total_nox, 6),
            rows=rows_out,
        )

    async def audit_ready_summary_csv(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> bytes:
        report = await self.audit_ready_summary(
            empresa_id=empresa_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        # Use manual buffer to keep dependencies minimal
        import io

        s = io.StringIO()
        w = csv.writer(s, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        w.writerow(
            [
                "periodo",
                "cliente_id",
                "cliente_nombre",
                "total_portes",
                "total_km_estimados",
                "total_co2_kg",
                "total_nox_kg",
                "metodologia",
            ]
        )
        for row in report.rows:
            w.writerow(
                [
                    row.periodo,
                    row.cliente_id,
                    row.cliente_nombre or "",
                    row.total_portes,
                    f"{row.total_km_estimados:.3f}",
                    f"{row.total_co2_kg:.6f}",
                    f"{row.total_nox_kg:.6f}",
                    row.metodologia,
                ]
            )
        return ("\ufeff" + s.getvalue()).encode("utf-8")

    async def suggest_vehicle_for_porte(
        self,
        *,
        empresa_id: str,
        km_estimados: float,
        long_route_km: float | None = None,
    ) -> dict[str, Any]:
        """
        Sugiere vehículo con menor CO₂ estimado (kg) para un porte.
        Prioriza Euro VI en rutas largas.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return {"vehiculo_id": None, "reason": "empresa_id inválido"}

        try:
            res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select("id, matricula, vehiculo, normativa_euro")
                    .eq("empresa_id", eid)
                )
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            rows = []

        if not rows:
            return {"vehiculo_id": None, "reason": "sin flota disponible"}

        km = max(0.0, float(km_estimados or 0.0))
        long_km = float(long_route_km or os.getenv("ESG_LONG_ROUTE_KM", "350"))

        best: dict[str, Any] | None = None
        for r in rows:
            norma = str(r.get("normativa_euro") or "Euro VI")
            factor = get_co2_factor_kg_per_km(norma)
            co2 = km * factor
            penalty = 0.0
            if km >= long_km and norma != "Euro VI":
                penalty = co2 * 0.08
            score = co2 + penalty
            candidate = {
                "vehiculo_id": str(r.get("id") or ""),
                "matricula": str(r.get("matricula") or ""),
                "vehiculo": str(r.get("vehiculo") or ""),
                "normativa_euro": norma,
                "co2_estimado_kg": round(co2, 6),
                "score": round(score, 6),
            }
            if best is None or candidate["score"] < best["score"]:
                best = candidate

        if best is None:
            return {"vehiculo_id": None, "reason": "sin candidatos"}

        return {
            "vehiculo_id": best["vehiculo_id"],
            "matricula": best["matricula"],
            "vehiculo": best["vehiculo"],
            "normativa_euro": best["normativa_euro"],
            "co2_estimado_kg": best["co2_estimado_kg"],
            "reason": "min_co2_with_eurovi_bias" if km >= long_km else "min_co2",
        }

    def calculate_emissions(
        self,
        litros: float,
        tipo_combustible: str = "Diesel A",
        *,
        certificacion_emisiones: str | None = None,
    ) -> float:
        """
        CO2 para combustible consumido.

        - Factor estándar: 1 litro Diesel A ≈ 2,67 kg CO2
        - Bonus Euro VI: si `certificacion_emisiones` es Euro VI, se reduce CO2
          según un % configurable (default: 15%).

        Nota: `certificacion_emisiones` se recomienda pasarlo desde `flota` para
        evitar consultas extra por fila.
        """
        try:
            l = max(0.0, float(litros))
        except (TypeError, ValueError):
            l = 0.0

        t = (tipo_combustible or "").strip().lower()
        # Hoy solo se usa Diesel A; mantenemos un fallback razonable.
        factor_kg_co2_por_litro = 2.67 if "diesel" in t else 2.67

        co2_kg = l * factor_kg_co2_por_litro

        cert = (certificacion_emisiones or "").strip()
        if cert.casefold() == "euro vi":
            bonus_pct = float(os.getenv("ESG_EUROVI_EMISSIONS_BONUS_PCT", "15"))
            bonus_pct = max(0.0, min(100.0, bonus_pct))
            co2_kg *= 1.0 - (bonus_pct / 100.0)

        return round(co2_kg, 6)
