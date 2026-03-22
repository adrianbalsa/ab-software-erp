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

# Factor estándar: emisiones de CO2 por litro de gasóleo (kg CO2eq / L) — referencia típica UE.
KG_CO2_POR_LITRO_DIESEL: float = float(os.getenv("ECO_KG_CO2_POR_LITRO_DIESEL") or "2.5")

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
        return EcoResumenLiteOut(
            n_tickets=full.n_tickets,
            papel_kg=full.papel_kg,
            co2_tickets=full.co2_tickets,
            co2_flota=full.co2_flota,
            co2_combustible=full.co2_combustible,
            co2_total=full.co2_total,
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
        Suma ``co2_emitido`` de portes con ``estado='facturado'`` cuya ``fecha`` cae en el mes calendario actual.
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
            )

        try:
            q = filter_not_deleted(
                self._db.table("portes")
                .select("co2_emitido, km_estimados, bultos, peso_ton")
                .eq("empresa_id", eid)
                .eq("estado", "facturado")
                .gte("fecha", fecha_ini.isoformat())
                .lte("fecha", fecha_fin.isoformat())
            )
            res: Any = await self._db.execute(q)
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            rows = []

        total = 0.0
        for r in rows:
            v = r.get("co2_emitido")
            if v is not None:
                try:
                    total += float(v)
                except (TypeError, ValueError):
                    pass
            else:
                total += co2_emitido_desde_porte_row(dict(r))

        return EcoDashboardOut(
            anio=y,
            mes=m,
            co2_kg_portes_facturados=round(total, 6),
            num_portes_facturados=len(rows),
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
