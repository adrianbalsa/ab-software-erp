from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.finance_service import (
    COSTE_OPERATIVO_EUR_KM,
    FinanceService,
    OTHER_NON_FUEL_OPEX_PER_KM,
    PorteFuelAllocation,
)
from app.schemas.bi import (
    BiDashboardSummaryOut,
    BiEsgImpactChartsOut,
    BiProfitabilityChartsOut,
    EsgMatrixPoint,
    HeatmapCellOut,
    ProfitabilityScatterPoint,
    TreemapNodeOut,
)

# Alineado con ``FinanceService`` (fallback sin tickets de combustible).
EFFICIENCY_DENOM_KM_FACTOR: float = COSTE_OPERATIVO_EUR_KM

_COMPLETED_ESTADOS = frozenset({"entregado", "facturado"})


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _parse_date_only(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()[:10]
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _km_aplicable_porte(row: dict[str, Any]) -> float:
    kr = row.get("km_reales")
    if kr is not None:
        return max(0.0, _to_float(kr))
    return max(0.0, _to_float(row.get("km_estimados")))


def _route_label(row: dict[str, Any]) -> str:
    o = str(row.get("origen_ciudad") or row.get("origen") or "").strip()
    d = str(row.get("destino_ciudad") or row.get("destino") or "").strip()
    if not o and not d:
        return "—"
    return f"{o[:40]} → {d[:40]}"


def _porte_estado_completed(raw: Any) -> bool:
    return str(raw or "").strip().lower() in _COMPLETED_ESTADOS


def _margen_estimado(row: dict[str, Any]) -> float:
    km = _km_aplicable_porte(row)
    precio = max(0.0, _to_float(row.get("precio_pactado")))
    return round(precio - km * COSTE_OPERATIVO_EUR_KM, 2)


async def _porte_pnl_by_id(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    date_from: date | None,
    date_to: date | None,
) -> dict[str, PorteFuelAllocation]:
    fin = FinanceService(db)
    d0 = date_from or date(1970, 1, 1)
    d1 = date_to or date.today()
    return await fin.link_expenses_to_portes(
        empresa_id=empresa_id,
        start_date=d0,
        end_date=d1,
        audit_trail=False,
    )


def _co2_kg_for_row(row: dict[str, Any]) -> float:
    raw = row.get("co2_kg")
    if raw is None:
        raw = row.get("co2_emitido")
    if raw is None:
        return max(0.0, _km_aplicable_porte(row) * EFFICIENCY_DENOM_KM_FACTOR)
    return max(0.0, _to_float(raw))


def _chunk_list(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _uuid_set(rows: list[dict[str, Any]], key: str) -> set[str]:
    out: set[str] = set()
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out.add(s)
    return out


def _flota_display(row: dict[str, Any]) -> str:
    mat = str(row.get("matricula") or "").strip()
    veh = str(row.get("vehiculo") or "").strip()
    if mat and veh:
        return f"{mat} · {veh}"
    return mat or veh or "—"


def _apply_porte_fecha_range(q: Any, date_from: date | None, date_to: date | None) -> Any:
    """Filtra portes por ``fecha`` del servicio (inclusive)."""
    if date_from is not None:
        q = q.gte("fecha", date_from.isoformat())
    if date_to is not None:
        q = q.lte("fecha", date_to.isoformat())
    return q


class BiService:
    """Agregados BI (finanzas + operaciones) con estructura orientada a Recharts."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def _fetch_portes_bi(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        base = filter_not_deleted(
            self._db.table("portes")
            .select(
                "id, estado, fecha, precio_pactado, km_estimados, km_reales, "
                "origen, destino, origen_ciudad, destino_ciudad, "
                "co2_kg, co2_emitido, esg_co2_ahorro_vs_euro_iii_kg"
            )
            .eq("empresa_id", empresa_id)
        )
        base = _apply_porte_fecha_range(base, date_from, date_to)
        try:
            res: Any = await self._db.execute(base)
        except Exception:
            res = await self._db.execute(
                _apply_porte_fecha_range(
                    filter_not_deleted(
                        self._db.table("portes")
                        .select(
                            "id, estado, fecha, precio_pactado, km_estimados, "
                            "origen, destino, origen_ciudad, destino_ciudad, "
                            "co2_kg, co2_emitido, esg_co2_ahorro_vs_euro_iii_kg"
                        )
                        .eq("empresa_id", empresa_id)
                    ),
                    date_from,
                    date_to,
                )
            )
        return (res.data or []) if hasattr(res, "data") else []

    async def _fetch_portes_for_scatter(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        base = filter_not_deleted(
            self._db.table("portes")
            .select(
                "id, estado, fecha, precio_pactado, km_estimados, km_reales, "
                "origen, destino, origen_ciudad, destino_ciudad, "
                "cliente_id, vehiculo_id"
            )
            .eq("empresa_id", empresa_id)
        )
        base = _apply_porte_fecha_range(base, date_from, date_to)
        try:
            res: Any = await self._db.execute(base)
        except Exception:
            res = await self._db.execute(
                _apply_porte_fecha_range(
                    filter_not_deleted(
                        self._db.table("portes")
                        .select(
                            "id, estado, fecha, precio_pactado, km_estimados, km_reales, "
                            "origen, destino, origen_ciudad, destino_ciudad, "
                            "cliente_id, vehiculo_id"
                        )
                        .eq("empresa_id", empresa_id)
                    ),
                    date_from,
                    date_to,
                )
            )
        return (res.data or []) if hasattr(res, "data") else []

    async def _batch_cliente_nombres(self, *, empresa_id: str, cliente_ids: set[str]) -> dict[str, str]:
        if not cliente_ids:
            return {}
        out: dict[str, str] = {}
        for chunk in _chunk_list(sorted(cliente_ids), 80):
            q = filter_not_deleted(
                self._db.table("clientes").select("id, nombre").eq("empresa_id", empresa_id).in_("id", chunk)
            )
            try:
                res: Any = await self._db.execute(q)
            except Exception:
                res = await self._db.execute(
                    self._db.table("clientes").select("id, nombre").eq("empresa_id", empresa_id).in_("id", chunk)
                )
            for r in (res.data or []) if hasattr(res, "data") else []:
                cid = str(r.get("id") or "").strip()
                if not cid:
                    continue
                nm = str(r.get("nombre") or "").strip()
                out[cid] = nm or "—"
        return out

    async def _batch_flota_labels(self, *, empresa_id: str, vehiculo_ids: set[str]) -> dict[str, str]:
        if not vehiculo_ids:
            return {}
        out: dict[str, str] = {}
        for chunk in _chunk_list(sorted(vehiculo_ids), 80):
            q = filter_not_deleted(
                self._db.table("flota").select("id, matricula, vehiculo").eq("empresa_id", empresa_id).in_("id", chunk)
            )
            try:
                res: Any = await self._db.execute(q)
            except Exception:
                res = await self._db.execute(
                    self._db.table("flota").select("id, matricula, vehiculo").eq("empresa_id", empresa_id).in_("id", chunk)
                )
            for r in (res.data or []) if hasattr(res, "data") else []:
                vid = str(r.get("id") or "").strip()
                if not vid:
                    continue
                out[vid] = _flota_display(r)
        return out

    async def _fetch_reconciled_invoice_rows(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        q = (
            self._db.table("facturas")
            .select("id, fecha_emision, matched_transaction_id, pago_id, estado_cobro")
            .eq("empresa_id", empresa_id)
            .eq("estado_cobro", "cobrada")
        )
        if date_from is not None:
            q = q.gte("fecha_emision", date_from.isoformat())
        if date_to is not None:
            q = q.lte("fecha_emision", date_to.isoformat())
        res: Any = await self._db.execute(q)
        rows = (res.data or []) if hasattr(res, "data") else []
        out: list[dict[str, Any]] = []
        for r in rows:
            mid = str(r.get("matched_transaction_id") or r.get("pago_id") or "").strip()
            if not mid:
                continue
            merged = dict(r)
            merged["matched_transaction_id"] = mid
            out.append(merged)
        return out

    async def _fetch_bank_booked_dates(
        self, *, empresa_id: str, transaction_ids: list[str]
    ) -> dict[str, date | None]:
        if not transaction_ids:
            return {}
        by_id: dict[str, date | None] = {}
        for chunk in _chunk_list(transaction_ids, 80):
            res: Any = await self._db.execute(
                self._db.table("bank_transactions")
                .select("transaction_id, booked_date, reconciled")
                .eq("empresa_id", empresa_id)
                .in_("transaction_id", chunk)
            )
            for row in (res.data or []) if hasattr(res, "data") else []:
                tid = str(row.get("transaction_id") or "").strip()
                if not tid:
                    continue
                by_id[tid] = _parse_date_only(row.get("booked_date"))
        return by_id

    def _compute_dso_days(self, facturas: list[dict[str, Any]], booked_by_tx: dict[str, date | None]) -> tuple[float | None, int]:
        deltas: list[int] = []
        for f in facturas:
            tid = str(f.get("matched_transaction_id") or "").strip()
            em = _parse_date_only(f.get("fecha_emision"))
            bd = booked_by_tx.get(tid)
            if em is None or bd is None:
                continue
            d = (bd - em).days
            if d < 0:
                d = 0
            deltas.append(d)
        if not deltas:
            return None, 0
        return round(sum(deltas) / len(deltas), 2), len(deltas)

    @staticmethod
    def _heatmap_bins(km: float, margin: float) -> tuple[str, str]:
        if km < 100:
            xb = "0–100 km"
        elif km < 300:
            xb = "100–300 km"
        elif km < 600:
            xb = "300–600 km"
        else:
            xb = "600+ km"

        if margin < 0:
            yb = "Margen < 0"
        elif margin < 200:
            yb = "0–200 €"
        elif margin < 500:
            yb = "200–500 €"
        elif margin < 1000:
            yb = "500–1000 €"
        else:
            yb = "1000+ €"
        return xb, yb

    async def dashboard_summary(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> BiDashboardSummaryOut:
        eid = str(empresa_id).strip()
        portes = await self._fetch_portes_bi(empresa_id=eid, date_from=date_from, date_to=date_to)
        completed = [p for p in portes if _porte_estado_completed(p.get("estado"))]

        dates_fecha = [_parse_date_only(p.get("fecha")) for p in completed]
        dates_ok = [d for d in dates_fecha if d is not None]
        d_min = min(dates_ok) if dates_ok else date.today() - timedelta(days=365)
        d_max = max(dates_ok) if dates_ok else date.today()
        pnl = await _porte_pnl_by_id(
            self._db, empresa_id=eid, date_from=d_min, date_to=d_max
        )

        margins: list[float] = []
        co2_saved_total = 0.0
        co2_saved_n = 0
        eff_vals: list[float] = []

        for p in completed:
            pid = str(p.get("id") or "").strip()
            row_pnl = pnl.get(pid) if pid else None
            m = row_pnl.margin_real_eur if row_pnl is not None else _margen_estimado(p)
            margins.append(m)
            ah = p.get("esg_co2_ahorro_vs_euro_iii_kg")
            if ah is not None:
                co2_saved_total += max(0.0, _to_float(ah))
                co2_saved_n += 1
            km = _km_aplicable_porte(p)
            price = max(0.0, _to_float(p.get("precio_pactado")))
            if row_pnl is not None and row_pnl.allocated_fuel_eur > 1e-9:
                eff_vals.append(price / row_pnl.allocated_fuel_eur)
            else:
                denom = km * EFFICIENCY_DENOM_KM_FACTOR
                if denom > 1e-9:
                    eff_vals.append(price / denom)

        fac_rows = await self._fetch_reconciled_invoice_rows(
            empresa_id=eid, date_from=date_from, date_to=date_to
        )
        tx_ids = sorted({str(r.get("matched_transaction_id") or "").strip() for r in fac_rows if r.get("matched_transaction_id")})
        booked = await self._fetch_bank_booked_dates(empresa_id=eid, transaction_ids=tx_ids)
        dso, dso_n = self._compute_dso_days(fac_rows, booked)

        return BiDashboardSummaryOut(
            dso_days=dso,
            dso_sample_size=dso_n,
            avg_margin_eur=round(sum(margins) / len(margins), 2) if margins else None,
            avg_margin_portes=len(margins),
            total_co2_saved_kg=round(co2_saved_total, 4) if co2_saved_n else None,
            co2_saved_portes=co2_saved_n,
            avg_efficiency_eur_per_eur_km=round(sum(eff_vals) / len(eff_vals), 4) if eff_vals else None,
            efficiency_sample_size=len(eff_vals),
        )

    async def profitability_scatter(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> BiProfitabilityChartsOut:
        eid = str(empresa_id).strip()
        portes = await self._fetch_portes_for_scatter(empresa_id=eid, date_from=date_from, date_to=date_to)
        d0 = date_from or date(1970, 1, 1)
        d1 = date_to or date.today()
        pnl = await _porte_pnl_by_id(self._db, empresa_id=eid, date_from=d0, date_to=d1)
        cids = _uuid_set(portes, "cliente_id")
        vids = _uuid_set(portes, "vehiculo_id")
        nombres_cli = await self._batch_cliente_nombres(empresa_id=eid, cliente_ids=cids)
        labels_fl = await self._batch_flota_labels(empresa_id=eid, vehiculo_ids=vids)
        points: list[ProfitabilityScatterPoint] = []
        for p in portes:
            if not _porte_estado_completed(p.get("estado")):
                continue
            km = _km_aplicable_porte(p)
            if km <= 0:
                continue
            pid = p.get("id")
            if pid is None:
                continue
            pid_s = str(pid).strip()
            row_pnl = pnl.get(pid_s)
            fuel_alloc: float | None
            other_opex: float | None
            if row_pnl is not None:
                margin = row_pnl.margin_real_eur
                m_legacy = row_pnl.margin_estimado_legacy_eur
                est_flag = row_pnl.estimated_fallback
                fuel_alloc = round(float(row_pnl.allocated_fuel_eur), 4)
                if not est_flag:
                    other_opex = round(km * OTHER_NON_FUEL_OPEX_PER_KM, 4)
                else:
                    other_opex = None
            else:
                margin = _margen_estimado(p)
                m_legacy = margin
                est_flag = True
                fuel_alloc = None
                other_opex = None
            cid = str(p.get("cliente_id") or "").strip()
            vid = str(p.get("vehiculo_id") or "").strip()
            points.append(
                ProfitabilityScatterPoint(
                    porte_id=UUID(str(pid)),
                    km=round(km, 4),
                    margin_eur=margin,
                    margin_estimado_legacy_eur=m_legacy,
                    estimated_margin=est_flag,
                    allocated_fuel_eur=fuel_alloc,
                    other_opex_eur=other_opex,
                    precio_pactado=_to_float(p.get("precio_pactado")) or None,
                    estado=str(p.get("estado") or "") or None,
                    cliente=nombres_cli.get(cid) if cid else None,
                    vehiculo=labels_fl.get(vid) if vid else None,
                    route_label=_route_label(p),
                )
            )
        return BiProfitabilityChartsOut(points=points, coste_operativo_eur_km=COSTE_OPERATIVO_EUR_KM)

    async def esg_impact_charts(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> BiEsgImpactChartsOut:
        eid = str(empresa_id).strip()
        portes = await self._fetch_portes_bi(empresa_id=eid, date_from=date_from, date_to=date_to)
        d0 = date_from or date(1970, 1, 1)
        d1 = date_to or date.today()
        pnl = await _porte_pnl_by_id(self._db, empresa_id=eid, date_from=d0, date_to=d1)
        matrix: list[EsgMatrixPoint] = []
        heat_acc: dict[tuple[str, str], dict[str, float | int]] = defaultdict(lambda: {"count": 0, "total_co2_kg": 0.0})
        treemap_nodes: list[TreemapNodeOut] = []

        for p in portes:
            if not _porte_estado_completed(p.get("estado")):
                continue
            pid = p.get("id")
            if pid is None:
                continue
            km = _km_aplicable_porte(p)
            co2 = _co2_kg_for_row(p)
            pid_s = str(pid).strip()
            row_pnl = pnl.get(pid_s)
            margen = row_pnl.margin_real_eur if row_pnl is not None else _margen_estimado(p)
            est_fb = row_pnl.estimated_fallback if row_pnl is not None else True
            label = _route_label(p)
            matrix.append(
                EsgMatrixPoint(
                    porte_id=UUID(str(pid)),
                    co2_kg=round(co2, 6),
                    margen_estimado=margen,
                    km=round(km, 4),
                    route_label=label,
                )
            )
            xb, yb = self._heatmap_bins(km, margen)
            cell = heat_acc[(xb, yb)]
            cell["count"] = int(cell["count"]) + 1
            cell["total_co2_kg"] = float(cell["total_co2_kg"]) + co2
            treemap_nodes.append(
                TreemapNodeOut(
                    name=label[:64] or str(pid)[:8],
                    size=round(co2, 6),
                    margen_estimado=margen,
                    porte_id=UUID(str(pid)),
                    estimated_fallback=est_fb,
                )
            )

        heatmap_cells = [
            HeatmapCellOut(
                x_bin=k[0],
                y_bin=k[1],
                count=int(v["count"]),
                total_co2_kg=round(float(v["total_co2_kg"]), 6),
            )
            for k, v in sorted(heat_acc.items(), key=lambda kv: (-int(kv[1]["count"]), kv[0][0], kv[0][1]))
        ]

        meta: dict[str, Any] = {
            "coste_operativo_eur_km": COSTE_OPERATIVO_EUR_KM,
            "completed_estados": sorted(_COMPLETED_ESTADOS),
        }
        if date_from is not None:
            meta["date_from"] = date_from.isoformat()
        if date_to is not None:
            meta["date_to"] = date_to.isoformat()
        return BiEsgImpactChartsOut(
            matrix=matrix,
            heatmap_cells=heatmap_cells,
            treemap_nodes=treemap_nodes,
            meta=meta,
        )
