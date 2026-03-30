from __future__ import annotations

from datetime import date
from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.finance import SimulationInput, SimulationResultOut, SimulationBreakEvenOut
from app.services.finance_service import FinanceService


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _periodo_yyyy_mm(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return None


def _last_n_month_keys(*, today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out: list[str] = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    out.reverse()
    return out


def _categoria_coste(categoria: str | None) -> str | None:
    c = str(categoria or "").strip().lower()
    if not c:
        return None
    if "combust" in c:
        return "combustible"
    if "peaje" in c:
        return "peajes"
    if (
        "personal" in c
        or "salario" in c
        or "nómina" in c
        or "nomina" in c
        or "sueldo" in c
        or "dieta" in c
        or "rrhh" in c
    ):
        return "salarios"
    return None


class SimulationService:
    """Motor de simulación de sensibilidad económica para dashboard financiero."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db
        self._finance = FinanceService(db)

    async def calcular_simulacion(
        self, *, empresa_id: str, params: SimulationInput
    ) -> SimulationResultOut:
        eid = str(empresa_id or "").strip()
        if not eid:
            raise ValueError("empresa_id es obligatorio")

        hoy = date.today()
        claves = set(_last_n_month_keys(today=hoy, n=3))

        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select("base_imponible, total_factura, cuota_iva, fecha_emision")
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []

        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []

        ingresos_base = 0.0
        for row in fact_rows:
            if _periodo_yyyy_mm(row.get("fecha_emision")) not in claves:
                continue
            ingresos_base += self._finance._ingreso_neto_sin_iva(row)

        gastos_base = 0.0
        costes_categoria_base: dict[str, float] = {
            "combustible": 0.0,
            "salarios": 0.0,
            "peajes": 0.0,
        }
        for row in gas_rows:
            if _periodo_yyyy_mm(row.get("fecha")) not in claves:
                continue
            neto = self._finance._gasto_neto_sin_iva(row)
            gastos_base += neto
            cat = _categoria_coste(row.get("categoria"))
            if cat is not None:
                costes_categoria_base[cat] += neto

        factores = {
            "combustible": 1.0 + (params.cambio_combustible_pct / 100.0),
            "salarios": 1.0 + (params.cambio_salarios_pct / 100.0),
            "peajes": 1.0 + (params.cambio_peajes_pct / 100.0),
        }

        costes_categoria_simulada = {
            key: round(costes_categoria_base[key] * factores[key], 2) for key in costes_categoria_base
        }

        delta_coste = sum(
            max(0.0, costes_categoria_simulada[key] - costes_categoria_base[key])
            for key in costes_categoria_base
        )
        # Si hay reducciones (porcentaje negativo), también deben impactar; mantenemos el delta real.
        delta_coste_real = sum(
            costes_categoria_simulada[key] - costes_categoria_base[key] for key in costes_categoria_base
        )

        ebitda_base = ingresos_base - gastos_base
        ebitda_simulado = ebitda_base - delta_coste_real
        impacto_eur = ebitda_simulado - ebitda_base
        impacto_pct = (impacto_eur / ebitda_base * 100.0) if abs(ebitda_base) > 1e-9 else 0.0
        impacto_mensual = impacto_eur / 3.0

        # Punto de ruptura: incremento de ingresos necesario para compensar el sobrecoste simulado.
        incremento_ingresos = delta_coste if delta_coste > 0 else 0.0
        tarifa_incremento_pct = (
            (incremento_ingresos / ingresos_base) * 100.0 if ingresos_base > 1e-9 else 0.0
        )

        return SimulationResultOut(
            periodo_meses=3,
            ingresos_base_eur=round(ingresos_base, 2),
            gastos_base_eur=round(gastos_base, 2),
            ebitda_base_eur=round(ebitda_base, 2),
            ebitda_simulado_eur=round(ebitda_simulado, 2),
            impacto_ebitda_eur=round(impacto_eur, 2),
            impacto_ebitda_pct=round(impacto_pct, 2),
            impacto_mensual_estimado_eur=round(impacto_mensual, 2),
            costes_categoria_base={k: round(v, 2) for k, v in costes_categoria_base.items()},
            costes_categoria_simulada=costes_categoria_simulada,
            break_even=SimulationBreakEvenOut(
                tarifa_incremento_pct=round(tarifa_incremento_pct, 2),
                incremento_ingresos_eur=round(incremento_ingresos, 2),
            ),
        )
