from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db.supabase import SupabaseAsync
from app.schemas.flota import (
    AmortizacionLinealIn,
    AmortizacionLinealOut,
    AmortizacionLineaOut,
    FlotaAlertaOut,
    FlotaAlertaPrioridad,
    FlotaEstadoActualOut,
    FlotaLiveTrackingOut,
    FlotaMetricasOut,
    FlotaVehiculoIn,
    FlotaVehiculoOut,
    LiveTrackingEstado,
    MantenimientoFlotaCreate,
)


def _parse_date_val(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if len(s) >= 10:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
    return None


def _priority_days(days_left: int) -> FlotaAlertaPrioridad:
    """Días hasta vencimiento (negativo = vencido)."""
    if days_left < 0:
        return "alta"
    if days_left <= 14:
        return "alta"
    if days_left <= 45:
        return "media"
    return "baja"


def _norm_matricula_key(raw: Any) -> str:
    """Clave estable para cruzar ``vehiculos.matricula`` con ``flota.matricula``."""
    s = str(raw or "").strip().upper()
    return "".join(c for c in s if c.isalnum())


def _priority_km(km_remaining: float) -> FlotaAlertaPrioridad:
    if km_remaining <= 0:
        return "alta"
    if km_remaining <= 1_000:
        return "media"
    return "baja"


def _alertas_for_row(row: dict[str, Any], *, today: date) -> list[FlotaAlertaOut]:
    """Genera 0..3 alertas por vehículo según proximidad. [cite: 2026-03-22]"""
    vid = str(row.get("id") or "").strip()
    if not vid:
        return []
    mat = (str(row.get("matricula") or "").strip() or None)
    nombre = (str(row.get("vehiculo") or "").strip() or None)
    out: list[FlotaAlertaOut] = []

    itv = _parse_date_val(row.get("itv_vencimiento"))
    if itv is not None:
        days = (itv - today).days
        if days <= 90 or days < 0:
            pr = _priority_days(days)
            det = (
                f"ITV {'vencida' if days < 0 else f'en {days} días'} ({itv.isoformat()})"
            )
            out.append(
                FlotaAlertaOut(
                    tipo="itv_vencimiento",
                    vehiculo_id=vid,
                    matricula=mat,
                    vehiculo=nombre,
                    prioridad=pr,
                    detalle=det,
                    fecha_referencia=itv,
                    km_restantes=None,
                )
            )

    seg = _parse_date_val(row.get("seguro_vencimiento"))
    if seg is not None:
        days = (seg - today).days
        if days <= 90 or days < 0:
            pr = _priority_days(days)
            det = (
                f"Seguro {'vencido' if days < 0 else f'vence en {days} días'} ({seg.isoformat()})"
            )
            out.append(
                FlotaAlertaOut(
                    tipo="seguro_vencimiento",
                    vehiculo_id=vid,
                    matricula=mat,
                    vehiculo=nombre,
                    prioridad=pr,
                    detalle=det,
                    fecha_referencia=seg,
                    km_restantes=None,
                )
            )

    km_act = float(row.get("km_actual") or 0)
    km_prox_raw = row.get("km_proximo_servicio")
    if km_prox_raw is not None:
        try:
            km_prox = float(km_prox_raw)
        except (TypeError, ValueError):
            km_prox = None
        if km_prox is not None:
            remaining = km_prox - km_act
            if remaining <= 3_000:
                pr = _priority_km(remaining)
                det = (
                    f"Revisión km: {'¡superada!' if remaining <= 0 else f'faltan {remaining:.0f} km'}"
                    f" (próx. a {km_prox:.0f} km)"
                )
                out.append(
                    FlotaAlertaOut(
                        tipo="proxima_revision_km",
                        vehiculo_id=vid,
                        matricula=mat,
                        vehiculo=nombre,
                        prioridad=pr,
                        detalle=det,
                        fecha_referencia=None,
                        km_restantes=float(remaining),
                    )
                )

    return out


_PR_ORDER = {"alta": 0, "media": 1, "baja": 2}


class FlotaService:
    """
    Service migrado desde `views/flota_view.py`.

    Incluye:
    - CRUD de inventario (tabla `flota`)
    - registro de mantenimiento (tabla `mantenimiento_flota`)
    - amortización lineal (simulador financiero)
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_inventario(self, *, empresa_id: str) -> list[FlotaVehiculoOut]:
        q = filter_not_deleted(self._db.table("flota").select("*").eq("empresa_id", empresa_id))
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[FlotaVehiculoOut] = []
        for row in rows:
            try:
                out.append(FlotaVehiculoOut(**row))
            except Exception:
                continue
        return out

    async def list_estado_actual(self, *, empresa_id: str) -> list[FlotaEstadoActualOut]:
        """
        Estado operativo para mapa en tiempo real.

        Objetivo principal: JOIN lógico `vehiculos` + `portes_activos` con forma exacta de `FleetMapTruck`.
        Fallback legacy: `flota` + `portes` (estado pendiente).
        """
        veh_rows: list[dict[str, Any]] = []
        try:
            qv = filter_not_deleted(
                self._db.table("vehiculos")
                .select("id,matricula,lat,lng,ultima_latitud,ultima_longitud,ultima_actualizacion_gps")
                .eq("empresa_id", empresa_id)
            )
            rveh: Any = await self._db.execute(qv)
            veh_rows = (rveh.data or []) if hasattr(rveh, "data") else []
        except Exception:
            try:
                qv = filter_not_deleted(
                    self._db.table("vehiculos").select("id,matricula,lat,lng").eq("empresa_id", empresa_id)
                )
                rveh = await self._db.execute(qv)
                veh_rows = (rveh.data or []) if hasattr(rveh, "data") else []
            except Exception:
                qv = filter_not_deleted(
                    self._db.table("flota").select("id,matricula,lat,lng").eq("empresa_id", empresa_id)
                )
                rveh = await self._db.execute(qv)
                veh_rows = (rveh.data or []) if hasattr(rveh, "data") else []

        veh_by_id: dict[str, dict[str, Any]] = {}
        veh_ids: list[str] = []
        for row in veh_rows:
            vid = str(row.get("id") or "").strip()
            if not vid:
                continue
            def _to_f(v: Any) -> float | None:
                if v is None:
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            ulat = _to_f(row.get("ultima_latitud"))
            ulng = _to_f(row.get("ultima_longitud"))
            plat = _to_f(row.get("lat"))
            plng = _to_f(row.get("lng"))
            lat = ulat if ulat is not None else plat
            lng = ulng if ulng is not None else plng
            if lat is None or lng is None:
                continue
            row = {**row, "lat": lat, "lng": lng}
            veh_by_id[vid] = row
            veh_ids.append(vid)

        if not veh_ids:
            return []

        porte_rows: list[dict[str, Any]] = []
        try:
            qp = filter_not_deleted(
                self._db.table("portes_activos")
                .select("id,vehiculo_id,origen,destino,margen_estimado")
                .eq("empresa_id", empresa_id)
                .in_("vehiculo_id", veh_ids)
            )
            rp: Any = await self._db.execute(qp)
            porte_rows = (rp.data or []) if hasattr(rp, "data") else []
        except Exception:
            qp = filter_not_deleted(
                self._db.table("portes")
                .select("id,vehiculo_id,origen,destino,precio_pactado")
                .eq("empresa_id", empresa_id)
                .eq("estado", "pendiente")
                .in_("vehiculo_id", veh_ids)
            )
            rp = await self._db.execute(qp)
            raw_rows = (rp.data or []) if hasattr(rp, "data") else []
            porte_rows = []
            for r in raw_rows:
                # Fallback de margen estimado cuando no existe la vista `portes_activos`.
                margen_estimado = float(r.get("precio_pactado") or 0.0)
                merged = dict(r)
                merged["margen_estimado"] = margen_estimado
                porte_rows.append(merged)

        # JOIN lógico vehículo -> primer porte activo asignado (1 camión = 1 porte en mapa operativo).
        porte_by_veh_id: dict[str, dict[str, Any]] = {}
        for row in porte_rows:
            veh_id = str(row.get("vehiculo_id") or "").strip()
            if not veh_id or veh_id in porte_by_veh_id:
                continue
            porte_by_veh_id[veh_id] = row

        out: list[FlotaEstadoActualOut] = []
        for veh_id, vrow in veh_by_id.items():
            prow = porte_by_veh_id.get(veh_id)
            if prow is None:
                continue
            try:
                out.append(
                    FlotaEstadoActualOut(
                        id=veh_id,
                        position={
                            "lat": float(vrow.get("lat")),
                            "lng": float(vrow.get("lng")),
                        },
                        porte={
                            "id": str(prow.get("id") or ""),
                            "origin": str(prow.get("origen") or ""),
                            "destination": str(prow.get("destino") or ""),
                            "estimatedMargin": float(prow.get("margen_estimado") or 0.0),
                        },
                    )
                )
            except Exception:
                continue
        return out

    async def save_inventario(
        self,
        *,
        empresa_id: str,
        vehiculos_in: list[FlotaVehiculoIn],
    ) -> list[FlotaVehiculoOut]:
        # 1) Borrados lógicos: si un id activo desaparece del payload, marcamos deleted_at.
        res_orig: Any = await self._db.execute(
            filter_not_deleted(self._db.table("flota").select("id").eq("empresa_id", empresa_id))
        )
        orig_rows: list[dict[str, Any]] = (res_orig.data or []) if hasattr(res_orig, "data") else []
        ids_originales = {str(r.get("id")) for r in orig_rows if r.get("id") is not None}

        ids_nuevos = {str(v.id) for v in vehiculos_in if v.id}
        ids_borrar = ids_originales - ids_nuevos
        for id_b in ids_borrar:
            await self._db.execute(
                self._db.table("flota")
                .update(soft_delete_payload())
                .eq("id", id_b)
                .eq("empresa_id", empresa_id)
                .is_("deleted_at", "null")
            )

        # 2) Upsert fila a fila (legacy: st.data_editor + upsert)
        for v in vehiculos_in:
            payload = v.model_dump(exclude_none=True)
            # Si es nuevo (sin id) eliminamos id para forzar insert.
            if payload.get("id") in (None, ""):
                payload.pop("id", None)
            payload["empresa_id"] = empresa_id
            payload["deleted_at"] = None  # reactivar vehículo si estaba borrado lógico
            await self._db.execute(self._db.table("flota").upsert(payload))

        # 3) Retornar el estado final desde DB
        return await self.list_inventario(empresa_id=empresa_id)

    async def add_mantenimiento(
        self,
        *,
        empresa_id: str,
        mantenimiento_in: MantenimientoFlotaCreate,
    ) -> dict[str, Any]:
        # Legacy: se guarda la matrícula en la columna `vehiculo`.
        payload: dict[str, Any] = {
            "empresa_id": empresa_id,
            "vehiculo": mantenimiento_in.vehiculo,
            "fecha": mantenimiento_in.fecha.isoformat(),
            "tipo": mantenimiento_in.tipo,
            "coste": float(mantenimiento_in.coste),
            "kilometros": float(mantenimiento_in.kilometros),
            "descripcion": mantenimiento_in.descripcion or "",
        }
        res: Any = await self._db.execute(self._db.table("mantenimiento_flota").insert(payload))
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return rows[0] if rows else payload

    async def amortizacion_lineal(self, *, payload: AmortizacionLinealIn) -> AmortizacionLinealOut:
        valor_inicial = float(payload.valor_inicial)
        valor_residual = float(payload.valor_residual)
        vida = int(payload.vida_util_anios)

        # Legacy (views/flota_view.py): sin "max" a >= 0.
        base_amortizable = valor_inicial - valor_residual
        cuota_anual = base_amortizable / float(vida) if vida > 0 else 0.0

        cuadro: list[AmortizacionLineaOut] = []
        acumulado = 0.0
        vnc = valor_inicial
        for anio in range(1, vida + 1):
            acumulado += cuota_anual
            vnc -= cuota_anual
            cuadro.append(
                AmortizacionLineaOut(
                    anio=anio,
                    cuota_anual=float(cuota_anual),
                    amort_acumulada=float(acumulado),
                    valor_neto_contable=float(vnc),
                )
            )

        return AmortizacionLinealOut(
            valor_inicial=float(valor_inicial),
            vida_util_anios=int(vida),
            valor_residual=float(valor_residual),
            base_amortizable=float(base_amortizable),
            cuota_anual=float(cuota_anual),
            cuadro=cuadro,
            serie_temporal=list(cuadro),
        )

    async def _list_fleet_rows_raw(self, *, empresa_id: str) -> list[dict[str, Any]]:
        q = filter_not_deleted(self._db.table("flota").select("*").eq("empresa_id", empresa_id))
        res: Any = await self._db.execute(q)
        return (res.data or []) if hasattr(res, "data") else []

    async def list_alertas(self, *, empresa_id: str) -> list[FlotaAlertaOut]:
        """
        Alertas ITV, seguro y próxima revisión por km (tabla ``flota``).
        Prioridad por proximidad (fecha o km restantes). [cite: 2026-03-22]
        """
        today = date.today()
        rows = await self._list_fleet_rows_raw(empresa_id=empresa_id)
        all_a: list[FlotaAlertaOut] = []
        for row in rows:
            all_a.extend(_alertas_for_row(dict(row), today=today))
        all_a.sort(key=lambda a: (_PR_ORDER.get(a.prioridad, 9), a.tipo))
        return all_a

    async def metricas_flota(self, *, empresa_id: str) -> FlotaMetricasOut:
        """
        % disponible vs % en riesgo de parada: riesgo = no operativo o alerta **alta**.
        """
        rows = await self._list_fleet_rows_raw(empresa_id=empresa_id)
        alerts = await self.list_alertas(empresa_id=empresa_id)
        alta_ids = {a.vehiculo_id for a in alerts if a.prioridad == "alta"}
        riesgo_ids: set[str] = set()
        for r in rows:
            rid = str(r.get("id") or "").strip()
            if not rid:
                continue
            est = str(r.get("estado") or "").strip()
            if est and est != "Operativo":
                riesgo_ids.add(rid)
            if rid in alta_ids:
                riesgo_ids.add(rid)
        total = len([r for r in rows if str(r.get("id") or "").strip()])
        en_riesgo = len(riesgo_ids)
        disponibles = max(0, total - en_riesgo)
        if total <= 0:
            return FlotaMetricasOut(
                total_vehiculos=0,
                en_riesgo_parada=0,
                disponibles=0,
                pct_disponible=0.0,
                pct_riesgo_parada=0.0,
            )
        pct_r = round(100.0 * en_riesgo / total, 1)
        pct_d = round(100.0 - pct_r, 1)
        return FlotaMetricasOut(
            total_vehiculos=total,
            en_riesgo_parada=en_riesgo,
            disponibles=disponibles,
            pct_disponible=pct_d,
            pct_riesgo_parada=pct_r,
        )

    def export_estado_flota_csv(self, *, empresa_id: str, rows: list[dict[str, Any]]) -> bytes:
        """CSV UTF-8 con BOM para Excel con vencimientos. [cite: 2026-03-22]"""
        today = date.today()
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        w.writerow(
            [
                "matricula",
                "vehiculo",
                "estado",
                "km_actual",
                "km_proximo_servicio",
                "itv_vencimiento",
                "seguro_vencimiento",
                "dias_hasta_itv",
                "dias_hasta_seguro",
                "km_hasta_revision",
                "empresa_id",
            ]
        )
        for row in rows:
            itv = _parse_date_val(row.get("itv_vencimiento"))
            seg = _parse_date_val(row.get("seguro_vencimiento"))
            d_itv = (itv - today).days if itv else ""
            d_seg = (seg - today).days if seg else ""
            km_a = float(row.get("km_actual") or 0)
            km_p = row.get("km_proximo_servicio")
            km_hasta = ""
            if km_p is not None:
                try:
                    km_hasta = f"{float(km_p) - km_a:.0f}"
                except (TypeError, ValueError):
                    km_hasta = ""
            w.writerow(
                [
                    row.get("matricula") or "",
                    row.get("vehiculo") or "",
                    row.get("estado") or "",
                    row.get("km_actual") or "",
                    row.get("km_proximo_servicio") or "",
                    itv.isoformat() if itv else "",
                    seg.isoformat() if seg else "",
                    d_itv,
                    d_seg,
                    km_hasta,
                    empresa_id,
                ]
            )
        return ("\ufeff" + buf.getvalue()).encode("utf-8")

    async def export_estado_flota_csv_bytes(self, *, empresa_id: str) -> bytes:
        rows = await self._list_fleet_rows_raw(empresa_id=empresa_id)
        return self.export_estado_flota_csv(empresa_id=empresa_id, rows=rows)

    async def update_ubicacion_gps(
        self,
        *,
        empresa_id: str,
        vehiculo_id: str,
        latitud: float,
        longitud: float,
    ) -> None:
        """Persiste última posición GPS en ``vehiculos`` (Fleet tracking)."""
        from datetime import datetime, timezone

        eid = str(empresa_id or "").strip()
        vid = str(vehiculo_id or "").strip()
        if not eid or not vid:
            raise ValueError("empresa_id y vehiculo_id son obligatorios")

        q = filter_not_deleted(
            self._db.table("vehiculos").select("id").eq("empresa_id", eid).eq("id", vid).limit(1)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Vehículo no encontrado")

        ts = datetime.now(timezone.utc).isoformat()
        payload = {
            "ultima_latitud": float(latitud),
            "ultima_longitud": float(longitud),
            "ultima_actualizacion_gps": ts,
        }
        await self._db.execute(
            filter_not_deleted(
                self._db.table("vehiculos").update(payload).eq("empresa_id", eid).eq("id", vid)
            )
        )

    async def list_live_tracking(self, *, empresa_id: str) -> list[FlotaLiveTrackingOut]:
        """
        Lista ultraligera de vehículos con última posición GPS y estado operativo
        (Disponible / En Ruta / Taller). Conductor vía ``profiles.assigned_vehiculo_id`` → ``flota.id``
        (misma matrícula que ``vehiculos``).
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return []

        veh_rows: list[dict[str, Any]] = []
        try:
            qv = filter_not_deleted(
                self._db.table("vehiculos")
                .select(
                    "id,matricula,lat,lng,ultima_latitud,ultima_longitud,ultima_actualizacion_gps"
                )
                .eq("empresa_id", eid)
            )
            rveh: Any = await self._db.execute(qv)
            veh_rows = (rveh.data or []) if hasattr(rveh, "data") else []
        except Exception:
            return []

        flota_by_mat: dict[str, dict[str, Any]] = {}
        try:
            qf = filter_not_deleted(
                self._db.table("flota").select("id,matricula,estado").eq("empresa_id", eid)
            )
            rf: Any = await self._db.execute(qf)
            for r in (rf.data or []) if hasattr(rf, "data") else []:
                if not isinstance(r, dict):
                    continue
                k = _norm_matricula_key(r.get("matricula"))
                if k and k not in flota_by_mat:
                    flota_by_mat[k] = dict(r)
        except Exception:
            pass

        porte_veh_ids: set[str] = set()
        try:
            qp = filter_not_deleted(
                self._db.table("portes")
                .select("vehiculo_id")
                .eq("empresa_id", eid)
                .eq("estado", "pendiente")
            )
            rp: Any = await self._db.execute(qp)
            for r in (rp.data or []) if hasattr(rp, "data") else []:
                if not isinstance(r, dict):
                    continue
                vid_p = str(r.get("vehiculo_id") or "").strip()
                if vid_p:
                    porte_veh_ids.add(vid_p)
        except Exception:
            pass

        conductor_by_flota_id: dict[str, str] = {}
        try:
            qpr: Any = await self._db.execute(
                self._db.table("profiles")
                .select("assigned_vehiculo_id,username,email")
                .eq("empresa_id", eid)
            )
            for pr in (qpr.data or []) if hasattr(qpr, "data") else []:
                if not isinstance(pr, dict):
                    continue
                aid = pr.get("assigned_vehiculo_id")
                if aid is None or not str(aid).strip():
                    continue
                fid = str(aid).strip()
                name = str(pr.get("username") or pr.get("email") or "").strip()
                if fid and name:
                    conductor_by_flota_id[fid] = name
        except Exception:
            pass

        def _to_f(v: Any) -> float | None:
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def _parse_ts(v: Any) -> datetime | None:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v
            s = str(v).strip()
            if not s:
                return None
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                return None

        out: list[FlotaLiveTrackingOut] = []
        for row in veh_rows:
            vid = str(row.get("id") or "").strip()
            if not vid:
                continue
            mat = str(row.get("matricula") or "").strip()
            mk = _norm_matricula_key(mat)
            flota_row = flota_by_mat.get(mk) if mk else None
            flota_id: str | None = None
            if flota_row and flota_row.get("id") is not None:
                flota_id = str(flota_row.get("id")).strip() or None

            estado_flota = str(flota_row.get("estado") or "").strip() if flota_row else ""
            estado: LiveTrackingEstado = "Disponible"
            if estado_flota == "En Taller":
                estado = "Taller"
            elif estado_flota in ("Baja", "Vendido"):
                estado = "Taller"
            elif (flota_id and flota_id in porte_veh_ids) or (vid in porte_veh_ids):
                estado = "En Ruta"

            ulat = _to_f(row.get("ultima_latitud"))
            ulng = _to_f(row.get("ultima_longitud"))
            plat = _to_f(row.get("lat"))
            plng = _to_f(row.get("lng"))
            lat_o = ulat if ulat is not None else plat
            lng_o = ulng if ulng is not None else plng

            ts = _parse_ts(row.get("ultima_actualizacion_gps"))

            conductor: str | None = None
            if flota_id:
                conductor = conductor_by_flota_id.get(flota_id)

            try:
                out.append(
                    FlotaLiveTrackingOut(
                        id=vid,
                        matricula=mat or "—",
                        estado=estado,
                        ultima_latitud=lat_o,
                        ultima_longitud=lng_o,
                        ultima_actualizacion_gps=ts,
                        conductor_nombre=conductor,
                    )
                )
            except Exception:
                continue
        return out
