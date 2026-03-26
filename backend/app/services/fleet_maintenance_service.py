from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.fleet_maintenance import (
    AlertaAdministrativaOut,
    MantenimientoAlertaOut,
    MantenimientoRegistrarIn,
    MantenimientoRegistrarOut,
    TramiteAdministrativo,
    clasificar_fecha_urgencia,
    clasificar_urgencia,
)
from app.schemas.gasto import GastoCreate
from app.services.gastos_service import GastosService

_log = logging.getLogger(__name__)


def _eid(empresa_id: str | UUID) -> str:
    return str(empresa_id).strip()


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


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _append_tramite(
    out: list[AlertaAdministrativaOut],
    *,
    vehiculo_id: str,
    matricula: str | None,
    vehiculo: str | None,
    tipo: TramiteAdministrativo,
    fecha: date | None,
    today: date,
) -> None:
    if fecha is None:
        return
    dias = (fecha - today).days
    urg = clasificar_fecha_urgencia(dias)
    try:
        out.append(
            AlertaAdministrativaOut(
                vehiculo_id=UUID(vehiculo_id),
                matricula=matricula,
                vehiculo=vehiculo,
                tipo_tramite=tipo,
                fecha_vencimiento=fecha,
                dias_restantes=dias,
                urgencia=urg,
            )
        )
    except Exception:
        _log.debug("alerta administrativa: fila omitida", exc_info=True)


class FleetMaintenanceService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def get_date_based_alerts(self, *, empresa_id: str | UUID) -> list[AlertaAdministrativaOut]:
        """
        Compara la fecha actual (UTC) con ITV, seguro y tacógrafo por vehículo.
        Usa ``fecha_*`` con fallback a columnas legacy ``itv_vencimiento`` / ``seguro_vencimiento``.
        """
        eid = _eid(empresa_id)
        today = _today_utc()
        res: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("flota").select(
                    "id, matricula, vehiculo, fecha_itv, fecha_seguro, fecha_tacografo, "
                    "itv_vencimiento, seguro_vencimiento"
                )
            ).eq("empresa_id", eid)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[AlertaAdministrativaOut] = []
        for row in rows:
            vid = str(row.get("id") or "").strip()
            if not vid:
                continue
            mat = str(row.get("matricula") or "").strip() or None
            nom = str(row.get("vehiculo") or "").strip() or None
            itv = _parse_date_val(row.get("fecha_itv")) or _parse_date_val(row.get("itv_vencimiento"))
            seg = _parse_date_val(row.get("fecha_seguro")) or _parse_date_val(row.get("seguro_vencimiento"))
            tac = _parse_date_val(row.get("fecha_tacografo"))
            _append_tramite(out, vehiculo_id=vid, matricula=mat, vehiculo=nom, tipo="ITV", fecha=itv, today=today)
            _append_tramite(out, vehiculo_id=vid, matricula=mat, vehiculo=nom, tipo="SEGURO", fecha=seg, today=today)
            _append_tramite(out, vehiculo_id=vid, matricula=mat, vehiculo=nom, tipo="TACOGRAFO", fecha=tac, today=today)

        out.sort(
            key=lambda x: (
                0 if x.urgencia == "CRITICO" else 1 if x.urgencia == "ADVERTENCIA" else 2,
                x.dias_restantes,
                x.tipo_tramite,
            )
        )
        return out

    async def list_alertas_mantenimiento(
        self, *, empresa_id: str | UUID
    ) -> list[MantenimientoAlertaOut | AlertaAdministrativaOut]:
        eid = _eid(empresa_id)
        res_p: Any = await self._db.execute(
            self._db.table("planes_mantenimiento")
            .select("id, empresa_id, vehiculo_id, tipo_tarea, intervalo_km, ultimo_km_realizado")
            .eq("empresa_id", eid)
        )
        planes: list[dict[str, Any]] = (res_p.data or []) if hasattr(res_p, "data") else []

        km_out: list[MantenimientoAlertaOut] = []
        by_vid: dict[str, dict[str, Any]] = {}
        if planes:
            vids = list({str(p.get("vehiculo_id")) for p in planes if p.get("vehiculo_id")})
            if vids:
                res_f: Any = await self._db.execute(
                    self._db.table("flota")
                    .select("id, matricula, vehiculo, odometro_actual, km_actual")
                    .eq("empresa_id", eid)
                    .in_("id", vids)
                )
                flota_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
                by_vid = {str(r.get("id")): r for r in flota_rows}

        for p in planes:
            pid = str(p.get("id") or "")
            vid = str(p.get("vehiculo_id") or "")
            iv = int(p.get("intervalo_km") or 0)
            ukm = int(p.get("ultimo_km_realizado") or 0)
            if iv <= 0:
                continue
            fr = by_vid.get(vid) or {}
            # Prefer odometro_actual; fallback km_actual for datos previos a la migración
            raw_odo = fr.get("odometro_actual")
            if raw_odo is None:
                raw_odo = fr.get("km_actual")
            odo = int(float(raw_odo or 0))
            km_desde = max(0, odo - ukm)
            desgaste = km_desde / float(iv)
            mat = str(fr.get("matricula") or "").strip() or None
            nom = str(fr.get("vehiculo") or "").strip() or None
            try:
                km_out.append(
                    MantenimientoAlertaOut(
                        plan_id=UUID(pid),
                        vehiculo_id=UUID(vid),
                        matricula=mat,
                        vehiculo=nom,
                        tipo_tarea=str(p.get("tipo_tarea") or ""),
                        intervalo_km=iv,
                        ultimo_km_realizado=ukm,
                        odometro_actual=odo,
                        km_desde_ultimo=km_desde,
                        desgaste=round(desgaste, 4),
                        urgencia=clasificar_urgencia(desgaste),
                    )
                )
            except Exception:
                _log.debug("alerta mantenimiento: fila omitida", exc_info=True)

        km_out.sort(
            key=lambda x: (
                0 if x.urgencia == "CRITICO" else 1 if x.urgencia == "ADVERTENCIA" else 2,
                -x.desgaste,
            )
        )
        date_out = await self.get_date_based_alerts(empresa_id=eid)

        def _merge_key(
            a: MantenimientoAlertaOut | AlertaAdministrativaOut,
        ) -> tuple[int, float]:
            u = 0 if a.urgencia == "CRITICO" else 1 if a.urgencia == "ADVERTENCIA" else 2
            if isinstance(a, MantenimientoAlertaOut):
                return (u, -a.desgaste)
            return (u, float(a.dias_restantes))

        merged: list[MantenimientoAlertaOut | AlertaAdministrativaOut] = [*km_out, *date_out]
        merged.sort(key=_merge_key)
        return merged

    async def registrar_mantenimiento(
        self,
        *,
        empresa_id: str | UUID,
        username_empleado: str,
        payload: MantenimientoRegistrarIn,
    ) -> MantenimientoRegistrarOut:
        eid = _eid(empresa_id)
        pid = str(payload.plan_id)

        res_p: Any = await self._db.execute(
            self._db.table("planes_mantenimiento")
            .select("id, empresa_id, vehiculo_id, tipo_tarea, intervalo_km, ultimo_km_realizado")
            .eq("id", pid)
            .eq("empresa_id", eid)
            .limit(1)
        )
        prow: list[dict[str, Any]] = (res_p.data or []) if hasattr(res_p, "data") else []
        if not prow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

        plan = prow[0]
        vid = str(plan.get("vehiculo_id") or "")

        res_f: Any = await self._db.execute(
            self._db.table("flota")
            .select("id, odometro_actual, km_actual, matricula")
            .eq("id", vid)
            .eq("empresa_id", eid)
            .limit(1)
        )
        frows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []
        if not frows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")

        fr = frows[0]
        raw_odo = fr.get("odometro_actual")
        if raw_odo is None:
            raw_odo = fr.get("km_actual")
        odo = int(float(raw_odo or 0))

        await self._db.execute(
            self._db.table("planes_mantenimiento")
            .update({"ultimo_km_realizado": odo})
            .eq("id", pid)
            .eq("empresa_id", eid)
        )

        mat = str(fr.get("matricula") or "").strip()
        tipo = str(plan.get("tipo_tarea") or "Mantenimiento")
        concepto = payload.concepto or f"{tipo} — vehículo {mat or vid[:8]}"

        gasto_in = GastoCreate(
            proveedor=payload.proveedor.strip(),
            fecha=date.today(),
            total_chf=float(payload.importe_eur),
            categoria="Mantenimiento flota",
            concepto=concepto[:2000],
            moneda="EUR",
            total_eur=float(payload.importe_eur),
        )
        gs = GastosService(self._db)
        gout = await gs.create_gasto(
            empresa_id=eid,
            empleado=username_empleado,
            gasto_in=gasto_in,
        )

        return MantenimientoRegistrarOut(
            plan_id=payload.plan_id,
            ultimo_km_realizado=odo,
            gasto_id=str(gout.id),
        )
