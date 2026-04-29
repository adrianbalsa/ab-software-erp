from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.esg import EsgPeriodSnapshotOut
from app.services.bi_service import BiService
from app.services.esg_service import EsgService
from app.services.finance_service import FinanceService


class LogisticsBrainContextService:
    """
    Construye un contexto unificado para asistentes IA, siempre aislado por tenant.
    """

    def __init__(
        self,
        finance: FinanceService,
        esg: EsgService,
        bi: BiService,
    ) -> None:
        self._finance = finance
        self._esg = esg
        self._bi = bi

    async def build(self, *, empresa_id: str) -> dict[str, Any]:
        eid = str(empresa_id or "").strip()
        if not eid:
            return {
                "financial": {},
                "esg_current": {},
                "esg_snapshots": [],
                "bi": {},
            }

        today = date.today()
        financial = await self._finance.financial_summary(empresa_id=eid)
        esg_current = await self._esg.calcular_huella_carbono_mensual(
            empresa_id=eid,
            mes=today.month,
            anio=today.year,
        )
        snapshots: list[EsgPeriodSnapshotOut] = await self._esg.list_esg_period_snapshots(
            empresa_id=eid,
            limit=12,
        )
        bi_summary = await self._bi.dashboard_summary(
            empresa_id=eid,
            date_from=date(today.year, 1, 1),
            date_to=today,
        )

        return {
            "financial": financial.model_dump(mode="json"),
            "esg_current": esg_current.model_dump(mode="json"),
            "esg_snapshots": [s.model_dump(mode="json") for s in snapshots],
            "bi": bi_summary.model_dump(mode="json"),
        }
