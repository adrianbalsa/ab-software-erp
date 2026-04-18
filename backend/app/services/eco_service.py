from __future__ import annotations

import calendar
import os
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.eco import (
    EcoCalculoIn,
    EcoDashboardOut,
    EcoEmisionMensualOut,
    EcoFlotaSimRow,
    EcoResumenLiteOut,
    EcoResumenOut,
    EcoSimuladorIn,
)
from app.schemas.porte import PorteCreate
from app.core.esg_engine import calculate_co2_footprint

# Factor estándar UE (Scope 1): emisiones de CO₂ por litro de gasóleo (kg CO₂eq / L), valor por defecto 2,67.
KG_CO2_POR_LITRO_DIESEL: float = float(os.getenv("ECO_KG_CO2_POR_LITRO_DIESEL") or "2.67")

# Precio referencia (EUR/L) para estimar litros a partir del importe de ticket de combustible.
EUR_POR_LITRO_DIESEL_REF: float = float(os.getenv("ECO_DIESEL_EUR_POR_LITRO_REF") or "1.55")

# Motor huella porte: kg CO2 ≈ km × t × factor (factor típico carretera, configurable).
ECO_TONELADAS_POR_BULTO: float = float(os.getenv("ECO_TONELADAS_POR_BULTO", "0.5"))


def factor_emision_huella_porte_default() -> float:
    return float(os.getenv("ECO_FACTOR_HUELLA_PORTE_KG_CO2_TKM") or "0.062")


def calcular_huella_porte(distancia_km: float, peso_ton: float, factor_emision: float) -> float:
    """CO₂ estimado (kg): distancia (km) × masa (t) × factor (kg CO₂ / (t·km))."""
    return float(distancia_km) * float(peso_ton) * float(factor_emision)


def peso_ton_desde_porte_row(row: dict[str, Any]) -> float:
    """Peso en toneladas: columna opcional `peso_ton` o estimación desde `bultos`."""
    pt = row.get("peso_ton")
    if pt is not None:
        try:
            return max(0.0, float(pt))
        except (TypeError, ValueError):
            pass
    try:
        b = float(row.get("bultos") or 1)
    except (TypeError, ValueError):
        b = 1.0
    return max(0.001, b * ECO_TONELADAS_POR_BULTO)


def peso_ton_desde_porte_create(porte_in: PorteCreate) -> float:
    if porte_in.peso_ton is not None:
        return max(0.0, float(porte_in.peso_ton))
    return max(0.001, float(porte_in.bultos) * ECO_TONELADAS_POR_BULTO)


def co2_emitido_desde_porte_row(row: dict[str, Any]) -> float:
    dist = float(row.get("km_estimados") or 0.0)
    peso = peso_ton_desde_porte_row(row)
    return calcular_huella_porte(dist, peso, factor_emision_huella_porte_default())


class EcoService:
    """
    ESG / sostenibilidad.

    - Tickets: papel + CO2 proxy por ticket digitalizado.
    - Flota: bonus CO2 por motor eléctrico/híbrido (legacy).
    - **Combustible (Scope 1)**: gastos con categoría ``COMBUSTIBLE`` → litros estimados
      (importe neto EUR / precio ref.) × factor kg CO2/L.
    """

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    @staticmethod
    def _periodo_yyyy_mm(val: Any) -> str | None:
        if val is None:
            return None
        s = str(val).strip()
        if len(s) >= 7 and s[4] == "-":
            return s[:7]
        return None

    async def _flota_attrs_by_id(
        self,
        *,
        empresa_id: str,
        ids: set[str],
    ) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        try:
            res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select("id, engine_class, fuel_type")
                    .eq("empresa_id", empresa_id)
                    .in_("id", list(ids))
                )
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            return {str(r.get("id")): r for r in rows if r.get("id") is not None}
        except Exception:
            return {}

    async def _dynamic_portes_emissions(
        self,
        *,
        empresa_id: str,
        period_month: str | None = None,
    ) -> tuple[float, float, float, float]:
        q = filter_not_deleted(
            self._db.table("portes")
            .select("vehiculo_id, km_estimados, km_vacio, subcontratado, peso_ton, bultos, fecha")
            .eq("empresa_id", empresa_id)
            .eq("estado", "facturado")
        )
        try:
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            rows = []

        if period_month:
            rows = [r for r in rows if self._periodo_yyyy_mm(r.get("fecha")) == period_month]

        veh_ids = {
            str(r.get("vehiculo_id")).strip()
            for r in rows
            if r.get("vehiculo_id") is not None and str(r.get("vehiculo_id")).strip()
        }
        flota_map = await self._flota_attrs_by_id(empresa_id=empresa_id, ids=veh_ids)

        total = 0.0
        scope1 = 0.0
        scope3 = 0.0
        ton_km = 0.0

        for r in rows:
            km_total = max(0.0, float(r.get("km_estimados") or 0.0))
            km_vacio = max(0.0, float(r.get("km_vacio") or 0.0))
            if km_vacio > km_total:
                km_vacio = km_total
            km_cargado = max(0.0, km_total - km_vacio)

            vid = str(r.get("vehiculo_id") or "").strip()
            attrs = flota_map.get(vid, {})
            engine_class = str(attrs.get("engine_class") or "EURO_VI")
            fuel_type = str(attrs.get("fuel_type") or "DIESEL")
            is_sub = bool(r.get("subcontratado") or False)

            co2 = calculate_co2_footprint(
                km_cargado=km_cargado,
                km_vacio=km_vacio,
                engine_class=engine_class,
                fuel_type=fuel_type,
                subcontratado=is_sub,
            )
            total += float(co2["total_co2_kg"])
            scope1 += float(co2["scope_1_kg"])
            scope3 += float(co2["scope_3_kg"])

            peso = peso_ton_desde_porte_row(r)
            ton_km += max(0.0, peso * km_cargado)

        intensity = (total / ton_km) if ton_km > 0 else 0.0
        return round(total, 6), round(scope1, 6), round(scope3, 6), round(intensity, 8)

    async def dynamic_portes_summary(
        self,
        *,
        empresa_id: str,
        period_month: str | None = None,
    ) -> tuple[float, float, float, float]:
        return await self._dynamic_portes_emissions(
            empresa_id=empresa_id,
            period_month=period_month,
        )

    @staticmethod
    def _categoria_es_combustible(raw: object) -> bool:
        if raw is None:
            return False
        return str(raw).strip().upper() == "COMBUSTIBLE"

    @staticmethod
    def _gasto_neto_eur(row: dict[str, Any]) -> float:
        """Importe en EUR neto de IVA (misma lógica que FinanceService)."""
        te = row.get("total_eur")
        gross = float(te) if te is not None else float(row.get("total_chf") or 0.0)
        iva_raw = row.get("iva")
        if iva_raw is None:
            return max(0.0, gross)
        try:
            iva_part = float(iva_raw)
        except (TypeError, ValueError):
            return max(0.0, gross)
        if iva_part <= 0:
            return max(0.0, gross)
        return max(0.0, gross - iva_part)

    @staticmethod
    def _parse_fecha_gasto(row: dict[str, Any]) -> date | None:
        raw = row.get("fecha")
        if raw is None:
            return None
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return raw
        if isinstance(raw, datetime):
            return raw.date()
        s = str(raw).strip()[:10]
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    def _litros_y_co2_desde_gasto(self, row: dict[str, Any]) -> tuple[float, float]:
        """
        Estima litros de diesel y kg CO2 a partir del gasto neto (EUR).

        Sin desglose de litros en ticket: litros ≈ neto_EUR / precio_ref_EUR/L.
        """
        neto = self._gasto_neto_eur(row)
        if neto <= 0 or EUR_POR_LITRO_DIESEL_REF <= 0:
            return 0.0, 0.0
        litros = neto / EUR_POR_LITRO_DIESEL_REF
        co2_kg = litros * KG_CO2_POR_LITRO_DIESEL
        return litros, co2_kg

    async def co2_emisiones_combustible_scope1(self, *, empresa_id: str) -> tuple[float, float]:
        """
        Total empresa (JWT): kg CO2 Scope 1 por combustible y litros estimados acumulados.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return 0.0, 0.0

        try:
            res: Any = await self._db.execute(
                filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            return 0.0, 0.0

        litros_tot = 0.0
        co2_tot = 0.0
        for r in rows:
            if not self._categoria_es_combustible(r.get("categoria")):
                continue
            litros, co2 = self._litros_y_co2_desde_gasto(r)
            litros_tot += litros
            co2_tot += co2
        return float(co2_tot), float(litros_tot)

    async def emisiones_combustible_por_mes(
        self, *, empresa_id: str
    ) -> list[EcoEmisionMensualOut]:
        """
        Desglose mensual de CO2 por combustible (para PDF certificado).
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return []

        try:
            res: Any = await self._db.execute(
                filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            return []

        por_mes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # co2, litros

        for r in rows:
            if not self._categoria_es_combustible(r.get("categoria")):
                continue
            fd = self._parse_fecha_gasto(r)
            if fd is None:
                periodo = date.today().strftime("%Y-%m")
            else:
                periodo = fd.strftime("%Y-%m")
            litros, co2 = self._litros_y_co2_desde_gasto(r)
            por_mes[periodo][0] += co2
            por_mes[periodo][1] += litros

        out: list[EcoEmisionMensualOut] = []
        for periodo in sorted(por_mes.keys()):
            co2_kg, lit = por_mes[periodo]
            out.append(
                EcoEmisionMensualOut(
                    periodo=periodo,
                    co2_kg=round(co2_kg, 3),
                    litros_estimados=round(lit, 3),
                )
            )
        return out

    @staticmethod
    def calcular_desde_inputs(*, payload: EcoCalculoIn) -> EcoResumenOut:
        n_tickets = int(payload.n_tickets)
        papel_kg = float(n_tickets) * 0.010
        co2_tickets = float(n_tickets) * 0.05

        co2_flota = 0.0
        for tipo in payload.tipos_motor or []:
            if str(tipo) in ["Eléctrico", "Híbrido"]:
                co2_flota += 150.0

        co2_combustible = 0.0
        co2_total = co2_tickets + co2_flota + co2_combustible
        return EcoResumenOut(
            n_tickets=n_tickets,
            papel_kg=float(papel_kg),
            co2_tickets=float(co2_tickets),
            co2_flota=float(co2_flota),
            co2_combustible=co2_combustible,
            co2_total=float(co2_total),
            flota_vehiculos=len(payload.tipos_motor or []),
        )

    @staticmethod
    def calcular_simulador_lite(*, payload: EcoSimuladorIn) -> EcoResumenLiteOut:
        full = EcoService.calcular_desde_inputs(
            payload=EcoCalculoIn(n_tickets=payload.n_tickets, tipos_motor=payload.tipos_motor)
        )
        return EcoResumenLiteOut(
            n_tickets=full.n_tickets,
            papel_kg=full.papel_kg,
            co2_tickets=full.co2_tickets,
            co2_flota=full.co2_flota,
            co2_combustible=full.co2_combustible,
            co2_total=full.co2_total,
            total_co2_kg=0.0,
            scope_1_kg=0.0,
            scope_3_kg=0.0,
            co2_per_ton_km=0.0,
        )

    async def resumen_empresa(self, *, empresa_id: str) -> EcoResumenOut:
        try:
            res_gas: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("gastos").select("id").eq("empresa_id", empresa_id)
                )
            )
            gastos_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []
            n_tickets = len(gastos_rows)
        except Exception:
            n_tickets = 0

        tipos_motor: list[str] = []
        try:
            res_flo: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota").select("tipo_motor").eq("empresa_id", empresa_id)
                )
            )
            flota_rows: list[dict[str, Any]] = (res_flo.data or []) if hasattr(res_flo, "data") else []
            for r in flota_rows:
                val = r.get("tipo_motor")
                if val:
                    tipos_motor.append(str(val))
        except Exception:
            tipos_motor = []

        base = self.calcular_desde_inputs(
            payload=EcoCalculoIn(n_tickets=n_tickets, tipos_motor=tipos_motor)
        )
        co2_comb, _litros = await self.co2_emisiones_combustible_scope1(empresa_id=empresa_id)
        co2_total = base.co2_tickets + base.co2_flota + co2_comb

        return EcoResumenOut(
            n_tickets=base.n_tickets,
            papel_kg=base.papel_kg,
            co2_tickets=base.co2_tickets,
            co2_flota=base.co2_flota,
            co2_combustible=float(co2_comb),
            co2_total=float(co2_total),
            flota_vehiculos=base.flota_vehiculos,
        )

    async def resumen_empresa_lite(self, *, empresa_id: str) -> EcoResumenLiteOut:
        full = await self.resumen_empresa(empresa_id=empresa_id)
        total_co2_kg, scope_1_kg, scope_3_kg, co2_per_ton_km = await self._dynamic_portes_emissions(
            empresa_id=str(empresa_id),
        )
        return EcoResumenLiteOut(
            n_tickets=full.n_tickets,
            papel_kg=full.papel_kg,
            co2_tickets=full.co2_tickets,
            co2_flota=full.co2_flota,
            co2_combustible=full.co2_combustible,
            co2_total=full.co2_total,
            total_co2_kg=total_co2_kg,
            scope_1_kg=scope_1_kg,
            scope_3_kg=scope_3_kg,
            co2_per_ton_km=co2_per_ton_km,
        )

    async def nombre_empresa_publico(self, *, empresa_id: str) -> str:
        """Nombre comercial o razón social para PDFs (solo datos de la empresa del JWT)."""
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

    async def obtener_reporte_mensual(self, *, empresa_id: str) -> EcoDashboardOut:
        """
        Emisiones dinámicas ESG de portes facturados del mes calendario actual.
        """
        eid = str(empresa_id or "").strip()
        today = date.today()
        y, m = today.year, today.month
        ultimo = calendar.monthrange(y, m)[1]
        fecha_ini = date(y, m, 1)
        fecha_fin = date(y, m, ultimo)

        if not eid:
            return EcoDashboardOut(
                anio=y,
                mes=m,
                co2_kg_portes_facturados=0.0,
                num_portes_facturados=0,
                scope_1_kg=0.0,
                scope_3_kg=0.0,
                co2_per_ton_km=0.0,
            )

        period_month = f"{y:04d}-{m:02d}"
        total, scope1, scope3, intensity = await self._dynamic_portes_emissions(
            empresa_id=eid,
            period_month=period_month,
        )
        try:
            q_count = filter_not_deleted(
                self._db.table("portes")
                .select("id")
                .eq("empresa_id", eid)
                .eq("estado", "facturado")
                .gte("fecha", fecha_ini.isoformat())
                .lte("fecha", fecha_fin.isoformat())
            )
            rc: Any = await self._db.execute(q_count)
            rows: list[dict[str, Any]] = (rc.data or []) if hasattr(rc, "data") else []
        except Exception:
            rows = []

        return EcoDashboardOut(
            anio=y,
            mes=m,
            co2_kg_portes_facturados=round(total, 6),
            num_portes_facturados=len(rows),
            scope_1_kg=scope1,
            scope_3_kg=scope3,
            co2_per_ton_km=intensity,
        )

    async def list_flota_simulador(self, *, empresa_id: str) -> list[EcoFlotaSimRow]:
        try:
            res_flo: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select("id, matricula, tipo_motor")
                    .eq("empresa_id", empresa_id)
                )
            )
            rows: list[dict[str, Any]] = (res_flo.data or []) if hasattr(res_flo, "data") else []
        except Exception:
            rows = []
        out: list[EcoFlotaSimRow] = []
        for r in rows:
            rid = r.get("id")
            mat = r.get("matricula")
            mot = r.get("tipo_motor")
            if rid is None or not mat:
                continue
            out.append(
                EcoFlotaSimRow(id=str(rid), matricula=str(mat), motor=str(mot or ""))
            )
        return out
