from __future__ import annotations

import calendar
import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
from typing import Any, Iterable
from uuid import UUID

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE
from app.core.i18n import get_translator
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.esg import (
    EsgAuditReadyOut,
    EsgAuditReadyRow,
    EsgMonthlyReportOut,
    EsgMonthlyReportRowOut,
    HuellaCarbonoMensualOut,
    PorteEmissionsCalculatedOut,
    RechartsBarPoint,
    SustainabilityReportOut,
    VehiculoHuellaMesOut,
)
from app.core.esg_engine import (
    calculate_co2_emissions,
    calculate_co2_footprint,
    calculate_nox_emissions,
    esg_certificate_co2_vs_euro_iii,
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

    @staticmethod
    def _to_decimal(value: Any, default: str = "0") -> Decimal:
        try:
            if value is None:
                return Decimal(default)
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def _q6(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    async def _fetch_factor_for_categoria(self, categoria_vehiculo: str) -> Decimal:
        categoria = str(categoria_vehiculo or "").strip()
        if not categoria:
            raise ValueError("Vehículo sin categoria_vehiculo")
        try:
            res: Any = await self._db.execute(
                self._db.table("estandares_emision_flota")
                .select("factor_emision_kg_km")
                .eq("categoria_vehiculo", categoria)
                .limit(1)
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            raise ValueError(f"No se pudo consultar estandares_emision_flota: {exc}") from exc
        if not rows:
            raise ValueError(f"No hay factor de emisión para categoría '{categoria}'")
        factor = self._to_decimal(rows[0].get("factor_emision_kg_km"), "0")
        if factor < 0:
            raise ValueError("El factor de emisión recuperado es inválido")
        return factor

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
                        "id, matricula, vehiculo, tipo_motor, factor_emision_co2_tkm, normativa_euro, engine_class, fuel_type"
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
                    "co2_emitido, fecha, km_vacio, subcontratado"
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
            km_vacio = max(0.0, float(r.get("km_vacio") or 0.0))
            if km_vacio > km_real:
                km_vacio = km_real
            km_cargado = max(0.0, km_real - km_vacio)
            co2_scoped = calculate_co2_footprint(
                km_cargado=km_cargado,
                km_vacio=km_vacio,
                engine_class=str((frow or {}).get("engine_class") or "EURO_VI"),
                fuel_type=str((frow or {}).get("fuel_type") or "DIESEL"),
                subcontratado=bool(r.get("subcontratado") or False),
            )
            co2_p = max(0.0, float(co2_scoped["total_co2_kg"]))
            co2_pess = max(0.0, co2_p * 1.15)

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

        # Hoy solo Diesel A; factor diésel ISO 14083 (kg CO₂eq/L).
        factor_kg_co2_por_litro = float(ISO_14083_DIESEL_CO2_KG_PER_LITRE)
        co2_kg = l * factor_kg_co2_por_litro

        cert = (certificacion_emisiones or "").strip()
        if cert.casefold() == "euro vi":
            bonus_pct = float(os.getenv("ESG_EUROVI_EMISSIONS_BONUS_PCT", "15"))
            bonus_pct = max(0.0, min(100.0, bonus_pct))
            co2_kg *= 1.0 - (bonus_pct / 100.0)

        return round(co2_kg, 6)

    @staticmethod
    def calculate_route_emissions(distance_km: float, factor_co2_km: float = 750.0) -> float:
        """
        Calcula emisiones por ruta en kg CO2.

        Formula:
            (distance_km * factor_co2_km) / 1000

        Donde ``factor_co2_km`` esta en gramos de CO2 por km.
        """
        try:
            km = max(0.0, float(distance_km))
        except (TypeError, ValueError):
            km = 0.0
        try:
            factor = max(0.0, float(factor_co2_km))
        except (TypeError, ValueError):
            factor = 750.0
        emisiones_kg = (km * factor) / 1000.0
        return round(emisiones_kg, 2)

    async def calculate_porte_emissions(self, porte_id: UUID) -> PorteEmissionsCalculatedOut:
        """
        CO₂e = (d / 1000) × EF × CF
        - d: ``real_distance_meters`` de ``portes``.
        - EF: ``estandares_emision_flota.factor_emision_kg_km`` según ``vehiculos.categoria_vehiculo``.
        - CF: load factor (por defecto 1.0).
        """
        pid = str(porte_id).strip()
        if not pid:
            raise ValueError("porte_id inválido")

        try:
            q = filter_not_deleted(
                self._db.table("portes")
                .select(
                    "id, empresa_id, real_distance_meters, vehiculo_id"
                )
                .eq("id", pid)
                .limit(1)
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            raise ValueError(f"No se pudo cargar el porte: {exc}") from exc

        if not rows:
            raise ValueError("Porte no encontrado")
        row = dict(rows[0])
        eid = str(row.get("empresa_id") or "").strip()
        if not eid:
            raise ValueError("Porte sin empresa_id")

        distance_meters = self._to_decimal(row.get("real_distance_meters"), "0")
        if distance_meters <= 0:
            raise ValueError("El porte no tiene real_distance_meters válido")

        vehiculo_id = str(row.get("vehiculo_id") or "").strip()
        if not vehiculo_id:
            raise ValueError("El porte no tiene vehiculo_id asignado")

        try:
            veh_res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("vehiculos")
                    .select("id,categoria_vehiculo")
                    .eq("empresa_id", eid)
                    .eq("id", vehiculo_id)
                    .limit(1)
                )
            )
            veh_rows: list[dict[str, Any]] = (veh_res.data or []) if hasattr(veh_res, "data") else []
        except Exception as exc:
            raise ValueError(f"No se pudo cargar vehículo del porte: {exc}") from exc
        if not veh_rows:
            raise ValueError("Vehículo del porte no encontrado")

        categoria_vehiculo = str(veh_rows[0].get("categoria_vehiculo") or "").strip()
        factor = await self._fetch_factor_for_categoria(categoria_vehiculo)
        load_factor = Decimal("1.0")
        co2_kg = self._q6((distance_meters / Decimal("1000")) * factor * load_factor)
        distance_km = self._q6(distance_meters / Decimal("1000"))

        try:
            await self._db.execute(
                self._db.table("portes")
                .update(
                    {
                        "co2_kg": str(co2_kg),
                        "co2_emitido": str(co2_kg),
                        "factor_emision_aplicado": str(self._q6(factor)),
                    }
                )
                .eq("id", pid)
                .eq("empresa_id", eid)
            )
        except Exception as exc:
            raise ValueError(f"No se pudo persistir co2_kg: {exc}") from exc

        return PorteEmissionsCalculatedOut(
            porte_id=pid,
            distance_km=float(distance_km),
            distance_confidence="high",
            weight_class=categoria_vehiculo,
            euro_vi_factor_kg_per_km=float(self._q6(factor)),
            co2_kg=float(co2_kg),
            factor_emision_aplicado=float(self._q6(factor)),
        )

    async def get_monthly_company_report(self, *, empresa_id: UUID | str) -> EsgMonthlyReportOut:
        eid = str(empresa_id).strip()
        if not eid:
            return EsgMonthlyReportOut(empresa_id="", rows=[])
        try:
            res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("portes")
                    .select("fecha,real_distance_meters,co2_kg,factor_emision_aplicado")
                    .eq("empresa_id", eid)
                )
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            raise ValueError(f"No se pudo generar reporte ESG mensual: {exc}") from exc

        agg: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {
                "total_portes": 0,
                "total_distance_km": Decimal("0"),
                "total_co2_kg": Decimal("0"),
                "sum_factor": Decimal("0"),
                "factor_count": 0,
            }
        )

        for row in rows:
            fecha_raw = str(row.get("fecha") or "").strip()
            if len(fecha_raw) < 7:
                continue
            month_key = fecha_raw[:7]
            distance_km = self._to_decimal(row.get("real_distance_meters"), "0") / Decimal("1000")
            co2_kg = self._to_decimal(row.get("co2_kg"), "0")
            factor = self._to_decimal(row.get("factor_emision_aplicado"), "0")

            bucket = agg[month_key]
            bucket["total_portes"] = int(bucket["total_portes"]) + 1
            bucket["total_distance_km"] = Decimal(bucket["total_distance_km"]) + max(Decimal("0"), distance_km)
            bucket["total_co2_kg"] = Decimal(bucket["total_co2_kg"]) + max(Decimal("0"), co2_kg)
            if factor > 0:
                bucket["sum_factor"] = Decimal(bucket["sum_factor"]) + factor
                bucket["factor_count"] = int(bucket["factor_count"]) + 1

        out_rows: list[EsgMonthlyReportRowOut] = []
        for month in sorted(agg.keys()):
            b = agg[month]
            factor_count = int(b["factor_count"])
            avg_factor = Decimal("0")
            if factor_count > 0:
                avg_factor = Decimal(b["sum_factor"]) / Decimal(str(factor_count))
            out_rows.append(
                EsgMonthlyReportRowOut(
                    month=month,
                    total_portes=int(b["total_portes"]),
                    total_distance_km=float(self._q6(Decimal(b["total_distance_km"]))),
                    total_co2_kg=float(self._q6(Decimal(b["total_co2_kg"]))),
                    avg_factor_emision=float(self._q6(avg_factor)),
                )
            )

        return EsgMonthlyReportOut(empresa_id=eid, rows=out_rows)

    async def get_company_sustainability_report(
        self,
        *,
        empresa_id: UUID | str,
        month: int,
        year: int,
    ) -> SustainabilityReportOut:
        """
        Informe mensual agregado: total CO₂ (GLEC) vs benchmark «ruta verde teórica»
        (km × factor km subóptimo × Euro VI ligero).
        """
        eid = str(empresa_id).strip()
        base = await self.calcular_huella_carbono_mensual(empresa_id=eid, mes=month, anio=year)

        try:
            green_km_factor = float(os.getenv("ESG_GREEN_ROUTE_KM_FACTOR", "0.93"))
        except (TypeError, ValueError):
            green_km_factor = 0.93
        green_km_factor = max(0.5, min(1.0, green_km_factor))

        km_eff = max(0.0, base.total_km_reales) * green_km_factor
        theoretical_green = km_eff * 0.70
        delta = round(float(base.total_co2_kg) - theoretical_green, 6)

        chart_comparison: list[RechartsBarPoint] = [
            RechartsBarPoint(
                name="Huella real (GLEC mensual)",
                value=round(float(base.total_co2_kg), 6),
                fill="#64748b",
            ),
            RechartsBarPoint(
                name="Referencia ruta verde (benchmark)",
                value=round(float(theoretical_green), 6),
                fill="#22c55e",
            ),
        ]

        chart_by_vehicle: list[dict[str, float | str | None]] = []
        for v in base.por_vehiculo:
            chart_by_vehicle.append(
                {
                    "name": v.etiqueta or v.matricula,
                    "co2_kg": round(float(v.co2_kg), 6),
                    "km": round(float(v.km_reales), 4),
                    "vehiculo_id": v.vehiculo_id,
                }
            )

        metodologia = (
            "Huella real: suma mensual con motor GLEC (km carretera vía Maps/caché, tramo cargado/vacío). "
            "Benchmark: mismos km ajustados por ESG_GREEN_ROUTE_KM_FACTOR (ruta subóptima vs ideal) "
            f"× {green_km_factor:.2f} × 0,70 kg CO₂/km (Euro VI clase ligera). Comparación orientativa, no sustituye verificación en laboratorio."
        )

        return SustainabilityReportOut(
            empresa_id=eid,
            year=year,
            month=month,
            total_co2_kg_actual=round(float(base.total_co2_kg), 6),
            total_km_reales=round(float(base.total_km_reales), 4),
            num_portes_facturados=int(base.num_portes_facturados),
            theoretical_green_route_co2_kg=round(float(theoretical_green), 6),
            green_route_km_factor=green_km_factor,
            co2_delta_vs_green_kg=delta,
            metodologia=metodologia,
            chart_comparison=chart_comparison,
            chart_by_vehicle=chart_by_vehicle,
        )


# ---------------------------------------------------------------------------
# Certificación comercial ISO 14083 + export CSV portal (misma lógica GLEC
# que ``esg_certificate_co2_vs_euro_iii`` / certificado PDF).
# ---------------------------------------------------------------------------
import io as _io
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors as _rl_colors
from reportlab.lib.pagesizes import A4 as _A4
from reportlab.lib.styles import ParagraphStyle as _ParagraphStyle, getSampleStyleSheet as _getSampleStyleSheet
from reportlab.lib.units import mm as _mm
from reportlab.platypus import Paragraph as _Paragraph, SimpleDocTemplate as _SimpleDocTemplate, Spacer as _Spacer, Table as _Table, TableStyle as _TableStyle

from app.services.pdf_esg_service import EsgPorteCertificatePdfModel


def diesel_co2eq_kg_from_litres(litros: float) -> float:
    """CO₂ equivalente (kg) a partir de litros de gasóleo × factor ISO 14083."""
    return max(0.0, float(litros or 0.0)) * float(ISO_14083_DIESEL_CO2_KG_PER_LITRE)


def generate_porte_certificate_pdf_reportlab(
    model: EsgPorteCertificatePdfModel, *, lang: str | None = None
) -> bytes:
    """PDF profesional (ReportLab) con ID porte, matrícula y referencia ISO 14083 (2,67 kg/L)."""
    t = get_translator(lang)
    buf = _io.BytesIO()
    doc = _SimpleDocTemplate(
        buf,
        pagesize=_A4,
        rightMargin=16 * _mm,
        leftMargin=16 * _mm,
        topMargin=14 * _mm,
        bottomMargin=14 * _mm,
        title=t("ESG certificate"),
    )
    styles = _getSampleStyleSheet()
    title_style = _ParagraphStyle(
        "EsgCertTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=8,
        textColor=_rl_colors.HexColor("#0f172a"),
    )
    body = _ParagraphStyle(
        "EsgCertBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=_rl_colors.HexColor("#334155"),
    )
    small = _ParagraphStyle(
        "EsgCertSmall",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=_rl_colors.HexColor("#64748b"),
    )

    matricula_guess = (model.vehiculo_label or "—").split("·")[0].strip() if model.vehiculo_label else "—"

    story: list[Any] = []
    story.append(_Paragraph(_xml_escape(t("Carbon footprint certificate — shipment")), title_style))
    story.append(
        _Paragraph(
            _xml_escape(t("AB Logistics OS · commercial audit document (GLEC v2.0; diesel factor ISO 14083).")),
            small,
        )
    )
    story.append(_Spacer(1, 6 * _mm))

    data_rows = [
        (t("Certificate ID"), model.certificate_id),
        (t("Content fingerprint (SHA-256)"), model.content_fingerprint_sha256[:48] + "…"),
        (t("Shipment ID"), model.porte_id),
        (t("Vehicle plate"), matricula_guess),
        (t("Vehicle"), model.vehiculo_label or "—"),
        (t("Operational date"), model.fecha),
        (t("Origin → Destination"), f"{model.origen} → {model.destino}"),
        (t("CO2 service (GLEC, kg CO2eq)"), f"{model.co2_total_kg:.6f}"),
        (t("Euro III baseline (kg CO2eq)"), f"{model.euro_iii_baseline_kg:.6f}"),
        (t("Savings vs Euro III (kg CO2eq)"), f"{model.ahorro_kg:.6f}"),
        (
            t("Diesel reference factor (ISO 14083)"),
            f"{ISO_14083_DIESEL_CO2_KG_PER_LITRE} kg CO₂eq / L",
        ),
        (t("Declared engine standard"), model.normativa_euro),
    ]
    tbl = _Table(
        [[_xml_escape(str(a)), _xml_escape(str(b))] for a, b in data_rows],
        colWidths=[52 * _mm, 118 * _mm],
    )
    tbl.setStyle(
        _TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _rl_colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, _rl_colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, _rl_colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(tbl)
    story.append(_Spacer(1, 5 * _mm))
    story.append(
        _Paragraph(
            _xml_escape(
                t("ISO 14083:2021 — diesel reference factor 2.67 kg CO2eq / L (audit / certificates).")
            ),
            body,
        )
    )
    story.append(_Spacer(1, 3 * _mm))
    story.append(
        _Paragraph(
            _xml_escape(
                t(
                    "GLEC CO2 figures match the BI dashboard and portal YTD CSV export for the same shipment and time window."
                )
            ),
            small,
        )
    )
    story.append(_Spacer(1, 4 * _mm))
    story.append(_Paragraph(_xml_escape(model.scope_note), body))

    doc.build(story)
    return buf.getvalue()


def _csv_escape_row(values: Iterable[str]) -> list[str]:
    return [str(v).replace("\r\n", " ").replace("\n", " ") for v in values]


ESG_CSV_COLUMNS = (
    "porte_id",
    "fecha",
    "estado",
    "matricula",
    "origen",
    "destino",
    "km_estimados",
    "km_vacio",
    "co2_total_kg_glec",
    "co2_euro_iii_baseline_kg",
    "co2_ahorro_vs_euro_iii_kg",
    "factor_diesel_iso14083_kg_per_l",
)

_PORTAL_ESG_YTD_STATES = frozenset({"entregado", "facturado"})


def _portal_esg_ytd_row_included(row: dict[str, Any]) -> bool:
    return str(row.get("estado") or "").strip().lower() in _PORTAL_ESG_YTD_STATES


def sum_portal_esg_co2_ahorro_kg(
    rows: list[dict[str, Any]], flota_by_id: dict[str, dict[str, Any]]
) -> float:
    """Suma ahorro CO₂ (GLEC vs Euro III) con la misma tripleta que CSV/certificado."""
    total = 0.0
    for r in rows:
        total += max(0.0, _esg_cert_kg_triplet(r, flota_by_id)[2])
    return round(total, 4)


async def _load_portal_cliente_esg_ytd_rows_flota(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    cliente_id: str,
    hoy: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], date]:
    eid = str(empresa_id or "").strip()
    cid = str(cliente_id or "").strip()
    if not eid or not cid:
        return ([], {}, date.today() if hoy is None else hoy)
    if hoy is None:
        hoy = date.today()
    d0 = date(hoy.year, 1, 1)

    query = filter_not_deleted(
        db.table("portes")
        .select("*")
        .eq("empresa_id", eid)
        .eq("cliente_id", cid)
        .gte("fecha", d0.isoformat())
        .lte("fecha", hoy.isoformat())
    )
    try:
        res: Any = await db.execute(query)
    except Exception:
        res = await db.execute(
            db.table("portes")
            .select("*")
            .eq("empresa_id", eid)
            .eq("cliente_id", cid)
            .gte("fecha", d0.isoformat())
            .lte("fecha", hoy.isoformat())
        )
    rows: list[dict[str, Any]] = [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]
    rows = [r for r in rows if _portal_esg_ytd_row_included(r)]

    vids = {str(r.get("vehiculo_id") or "").strip() for r in rows}
    vids.discard("")
    flota = await _batch_flota_for_esg_export(db, empresa_id=eid, vehiculo_ids=vids)
    return rows, flota, hoy


async def portal_cliente_esg_ytd_co2_ahorro_kg(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    cliente_id: str,
    hoy: date | None = None,
) -> float:
    """Ahorro CO₂ YTD portal = suma columna ``co2_ahorro_vs_euro_iii_kg`` del CSV (misma ventana y estados)."""
    rows, flota, _ = await _load_portal_cliente_esg_ytd_rows_flota(
        db, empresa_id=empresa_id, cliente_id=cliente_id, hoy=hoy
    )
    if not rows:
        return 0.0
    return sum_portal_esg_co2_ahorro_kg(rows, flota)


async def _batch_flota_for_esg_export(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    vehiculo_ids: set[str],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    ids = sorted(x for x in vehiculo_ids if x)
    if not ids:
        return out
    chunk_size = 60
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        try:
            res: Any = await db.execute(
                filter_not_deleted(
                    db.table("flota")
                    .select(
                        "id, matricula, vehiculo, normativa_euro, certificacion_emisiones, engine_class, fuel_type"
                    )
                    .eq("empresa_id", empresa_id)
                    .in_("id", chunk)
                )
            )
        except Exception:
            res = await db.execute(
                db.table("flota")
                .select(
                    "id, matricula, vehiculo, normativa_euro, certificacion_emisiones, engine_class, fuel_type"
                )
                .eq("empresa_id", empresa_id)
                .in_("id", chunk)
            )
        for r in (res.data or []) if hasattr(res, "data") else []:
            rid = str(r.get("id") or "").strip()
            if rid:
                out[rid] = dict(r)
    return out


def _esg_cert_kg_triplet(porte: dict[str, Any], flota_by_id: dict[str, dict[str, Any]]) -> tuple[float, float, float]:
    vid = str(porte.get("vehiculo_id") or "").strip()
    fr = flota_by_id.get(vid) or {}
    ec_raw = fr.get("engine_class")
    ft_raw = fr.get("fuel_type")
    ec = str(ec_raw).strip() if ec_raw not in (None, "") else None
    ft = str(ft_raw).strip() if ft_raw not in (None, "") else None
    cert = esg_certificate_co2_vs_euro_iii(
        km_estimados=float(porte.get("km_estimados") or 0.0),
        km_vacio=porte.get("km_vacio"),
        engine_class=ec,
        fuel_type=ft,
        subcontratado=bool(porte.get("subcontratado")),
    )
    return (
        float(cert["actual_total_kg"]),
        float(cert["euro_iii_baseline_kg"]),
        float(cert["ahorro_kg"]),
    )


async def portal_cliente_esg_ytd_csv(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    cliente_id: str,
    hoy: date | None = None,
) -> tuple[str, str]:
    """CSV YTD con CO₂ GLEC = certificado PDF (misma fórmula)."""
    eid = str(empresa_id or "").strip()
    cid = str(cliente_id or "").strip()
    if not eid or not cid:
        return ("esg_export_empty.csv", "")
    rows, flota, hoy = await _load_portal_cliente_esg_ytd_rows_flota(
        db, empresa_id=eid, cliente_id=cid, hoy=hoy
    )

    out_io = _io.StringIO()
    w = csv.writer(out_io)
    w.writerow(list(ESG_CSV_COLUMNS))
    fac_num = f"{ISO_14083_DIESEL_CO2_KG_PER_LITRE:.2f}"
    for r in sorted(rows, key=lambda x: str(x.get("fecha") or "")):
        vid = str(r.get("vehiculo_id") or "").strip()
        fr = flota.get(vid) or {}
        mat = str(fr.get("matricula") or "").strip() or "—"
        co2_t, co2_b, co2_a = _esg_cert_kg_triplet(r, flota)
        w.writerow(
            _csv_escape_row(
                [
                    str(r.get("id") or ""),
                    str(r.get("fecha") or "")[:10],
                    str(r.get("estado") or ""),
                    mat,
                    str(r.get("origen") or ""),
                    str(r.get("destino") or ""),
                    str(float(r.get("km_estimados") or 0.0)),
                    str(float(r.get("km_vacio") or 0.0) if r.get("km_vacio") is not None else ""),
                    f"{co2_t:.6f}",
                    f"{co2_b:.6f}",
                    f"{co2_a:.6f}",
                    fac_num,
                ]
            )
        )
    fname = f"esg_portal_ytd_{hoy.year}_{cid[:8]}.csv"
    return fname, out_io.getvalue()
