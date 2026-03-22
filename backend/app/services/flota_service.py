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
    FlotaMetricasOut,
    FlotaVehiculoIn,
    FlotaVehiculoOut,
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
