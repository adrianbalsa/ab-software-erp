from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.models.enums import UserRole
from app.schemas.geo_activity import GeoActivityPunto, GeoActivityResponse, GeoHeatCell
from app.schemas.user import UserOut

_log = logging.getLogger(__name__)

_GEO_BUCKET_PRECISION = 2
_MAX_PORTES_GLOBAL = 4000
_MAX_PORTES_TENANT = 2000
_MAX_PORTES_PORTAL = 80


def _geo_bucket(lat: float, lng: float, *, precision: int = _GEO_BUCKET_PRECISION) -> tuple[float, float]:
    return round(float(lat), precision), round(float(lng), precision)


def _as_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x


def _margen_visible(user: UserOut) -> bool:
    return user.rbac_role.strip().lower() != "traffic_manager"


async def _fetch_gastos_totals_by_porte(
    db: SupabaseAsync,
    *,
    empresa_id: str | None,
    porte_ids: list[str],
) -> dict[str, float]:
    if not porte_ids:
        return {}
    totals: dict[str, float] = defaultdict(float)
    chunk_size = 120
    for i in range(0, len(porte_ids), chunk_size):
        chunk = porte_ids[i : i + chunk_size]
        try:
            q = filter_not_deleted(
                db.table("gastos")
                .select("porte_id,total_eur,empresa_id")
                .in_("porte_id", chunk)
            )
            if empresa_id:
                q = q.eq("empresa_id", empresa_id)
            res: Any = await db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception as exc:
            _log.warning("geo_activity gastos batch: %s", exc)
            continue
        for row in rows:
            pid = str(row.get("porte_id") or "").strip()
            if not pid:
                continue
            te = _as_float(row.get("total_eur"))
            if te is not None and te > 0:
                totals[pid] += te
    return dict(totals)


def _margen_for_porte(
    row: dict[str, Any],
    gastos_by_porte: dict[str, float],
    *,
    show_margin: bool,
) -> float | None:
    if not show_margin:
        return None
    precio = _as_float(row.get("precio_pactado"))
    if precio is None:
        precio = 0.0
    pid = str(row.get("id") or "").strip()
    gastos = float(gastos_by_porte.get(pid, 0.0))
    return round(precio - gastos, 2)


def _rows_to_puntos(
    rows: Iterable[dict[str, Any]],
    gastos_by_porte: dict[str, float],
    *,
    show_margin: bool,
    solo_entrega: bool = False,
) -> list[GeoActivityPunto]:
    puntos: list[GeoActivityPunto] = []
    for row in rows:
        pid_raw = row.get("id")
        if pid_raw is None:
            continue
        try:
            pid = UUID(str(pid_raw))
        except ValueError:
            continue
        margen = _margen_for_porte(row, gastos_by_porte, show_margin=show_margin)

        if not solo_entrega:
            lo = _as_float(row.get("lat_origin"))
            go = _as_float(row.get("lng_origin"))
            if lo is not None and go is not None:
                puntos.append(
                    GeoActivityPunto(
                        id_porte=pid,
                        latitud=lo,
                        longitud=go,
                        tipo_evento="recogida",
                        margen_operativo=margen,
                    )
                )

        ld = _as_float(row.get("lat_dest"))
        gd = _as_float(row.get("lng_dest"))
        if ld is not None and gd is not None:
            puntos.append(
                GeoActivityPunto(
                    id_porte=pid,
                    latitud=ld,
                    longitud=gd,
                    tipo_evento="entrega",
                    margen_operativo=margen,
                )
            )
    return puntos


def _build_heatmap_cells(
    rows: list[dict[str, Any]],
    gastos_by_porte: dict[str, float],
) -> list[GeoHeatCell]:
    """
    Agrupa por destino de entrega (geostamp destino). ``ticket_gasto_medio`` = media de gastos
    totales por porte en la celda (proxy de ticket asociado a la zona).
    """
    by_bucket: dict[tuple[float, float], list[str]] = defaultdict(list)
    for row in rows:
        ld = _as_float(row.get("lat_dest"))
        gd = _as_float(row.get("lng_dest"))
        if ld is None or gd is None:
            continue
        pid = str(row.get("id") or "").strip()
        if not pid:
            continue
        b = _geo_bucket(ld, gd)
        by_bucket[b].append(pid)

    if not by_bucket:
        return []

    counts = [len(v) for v in by_bucket.values()]
    max_c = max(counts) if counts else 1

    cells: list[GeoHeatCell] = []
    for (lat, lng), pids in by_bucket.items():
        n = len(pids)
        gastos_vals = [float(gastos_by_porte.get(p, 0.0)) for p in pids]
        # Solo portes con gasto > 0 entran en la media de “ticket”; si ninguno, 0.
        with_g = [g for g in gastos_vals if g > 0]
        ticket_medio = round(sum(with_g) / len(with_g), 2) if with_g else 0.0
        cells.append(
            GeoHeatCell(
                latitud=lat,
                longitud=lng,
                intensidad=round(n / max_c, 4) if max_c else 0.0,
                portes_en_celda=n,
                ticket_gasto_medio=ticket_medio,
            )
        )
    return cells


class GeoActivityService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def load_for_user(self, user: UserOut) -> GeoActivityResponse:
        show_margin = _margen_visible(user)

        if user.role == UserRole.CLIENTE:
            return await self._portal_cliente(user, show_margin=show_margin)

        if user.role in {UserRole.SUPERADMIN, UserRole.DEVELOPER}:
            return await self._platform_admin(show_margin=show_margin)

        if user.role in {UserRole.ADMIN, UserRole.GESTOR}:
            return await self._tenant_staff(user, show_margin=show_margin)

        msg = "Rol sin acceso a geo-activity"
        raise ValueError(msg)

    async def _portal_cliente(self, user: UserOut, *, show_margin: bool) -> GeoActivityResponse:
        cid = user.cliente_id
        if cid is None:
            return GeoActivityResponse(puntos=[], heatmap=None)
        eid = str(user.empresa_id).strip()
        cid_s = str(cid).strip()
        q = filter_not_deleted(
            self._db.table("portes")
            .select(
                "id,precio_pactado,lat_origin,lng_origin,lat_dest,lng_dest,estado,fecha_entrega_real"
            )
            .eq("empresa_id", eid)
            .eq("cliente_id", cid_s)
            .in_("estado", ["Entregado", "facturado"])
            .order("fecha_entrega_real", desc=True)
            .limit(_MAX_PORTES_PORTAL)
        )
        res: Any = await self._db.execute(q)
        rows = [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]
        ids = [str(r["id"]) for r in rows if r.get("id")]
        gastos = await _fetch_gastos_totals_by_porte(self._db, empresa_id=eid, porte_ids=ids)
        # Portal: foco en entregas (destino); últimos portes ya vienen ordenados.
        puntos_entrega: list[GeoActivityPunto] = []
        for row in rows:
            pid_raw = row.get("id")
            if pid_raw is None:
                continue
            try:
                pid = UUID(str(pid_raw))
            except ValueError:
                continue
            ld = _as_float(row.get("lat_dest"))
            gd = _as_float(row.get("lng_dest"))
            if ld is None or gd is None:
                continue
            margen = _margen_for_porte(row, gastos, show_margin=show_margin)
            puntos_entrega.append(
                GeoActivityPunto(
                    id_porte=pid,
                    latitud=ld,
                    longitud=gd,
                    tipo_evento="entrega",
                    margen_operativo=margen,
                )
            )
        return GeoActivityResponse(puntos=puntos_entrega, heatmap=None)

    async def _tenant_staff(self, user: UserOut, *, show_margin: bool) -> GeoActivityResponse:
        eid = str(user.empresa_id).strip()
        q = filter_not_deleted(
            self._db.table("portes")
            .select(
                "id,precio_pactado,lat_origin,lng_origin,lat_dest,lng_dest,estado,fecha,fecha_entrega_real"
            )
            .eq("empresa_id", eid)
            .order("fecha", desc=True)
            .limit(_MAX_PORTES_TENANT)
        )
        res: Any = await self._db.execute(q)
        rows = [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]
        ids = [str(r["id"]) for r in rows if r.get("id")]
        gastos = await _fetch_gastos_totals_by_porte(self._db, empresa_id=eid, porte_ids=ids)
        puntos = _rows_to_puntos(rows, gastos, show_margin=show_margin, solo_entrega=False)
        heat_rows = [
            r
            for r in rows
            if _as_float(r.get("lat_dest")) is not None and _as_float(r.get("lng_dest")) is not None
        ]
        heatmap = _build_heatmap_cells(heat_rows, gastos)
        return GeoActivityResponse(puntos=puntos, heatmap=heatmap)

    async def _platform_admin(self, user: UserOut, *, show_margin: bool) -> GeoActivityResponse:
        _ = user
        q = filter_not_deleted(
            self._db.table("portes")
            .select(
                "id,precio_pactado,lat_origin,lng_origin,lat_dest,lng_dest,estado,fecha,fecha_entrega_real"
            )
            .order("fecha", desc=True)
            .limit(_MAX_PORTES_GLOBAL)
        )
        res: Any = await self._db.execute(q)
        rows = [dict(r) for r in ((res.data or []) if hasattr(res, "data") else [])]
        ids = [str(r["id"]) for r in rows if r.get("id")]
        gastos = await _fetch_gastos_totals_by_porte(self._db, empresa_id=None, porte_ids=ids)
        puntos = _rows_to_puntos(rows, gastos, show_margin=show_margin, solo_entrega=False)
        heat_rows = [
            r
            for r in rows
            if _as_float(r.get("lat_dest")) is not None and _as_float(r.get("lng_dest")) is not None
        ]
        heatmap = _build_heatmap_cells(heat_rows, gastos)
        return GeoActivityResponse(puntos=puntos, heatmap=heatmap)
