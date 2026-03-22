from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.esg import HuellaCarbonoMensualOut, VehiculoHuellaMesOut
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
                    .select("id, matricula, vehiculo, tipo_motor, factor_emision_co2_tkm")
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
                km_real = float(await self._maps.get_distance_km(origen, destino))
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
