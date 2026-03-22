from __future__ import annotations

from pydantic import BaseModel


class DashboardStatsOut(BaseModel):
    ebitda_estimado: float
    pendientes_cobro: float
    km_totales_mes: float
    bultos_mes: int

