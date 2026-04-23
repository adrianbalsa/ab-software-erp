"""
Integración GoCardless (Open Banking) — fachada de aplicación.

Los secretos se resuelven vía ``SecretManagerService`` (Vault / AWS / entorno → ``SaaSEnvSecretProvider``).
La persistencia y llamadas HTTP reutilizan ``BankService``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db.supabase import SupabaseAsync
from app.services.bank_service import BankService, BankSyncResult, _gocardless_configured
from app.services.secret_manager_service import get_secret_manager


class BankingService:
    """API estable: consentimiento + lectura de movimientos (GoCardless Bank Account Data v2)."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._bank = BankService(db)

    @staticmethod
    def secrets_configured() -> bool:
        """True si hay ``secret_id`` y ``secret_key`` disponibles (cualquier backend del gestor)."""
        return _gocardless_configured()

    @staticmethod
    def secret_manager_diagnostics() -> dict[str, bool]:
        """Metadatos mínimos para health checks (sin exponer secretos)."""
        m = get_secret_manager()
        return {
            "gocardless_secret_id_present": bool(m.get_gocardless_secret_id()),
            "gocardless_secret_key_present": bool(m.get_gocardless_secret_key()),
        }

    async def create_requisition(
        self,
        *,
        institution_id: str,
        empresa_id: str | None = None,
        redirect_url: str | None = None,
        requisition_id: str | None = None,
    ) -> dict[str, str]:
        """Crea requisición GoCardless y persiste IDs cifrados (flujo de consentimiento)."""
        if requisition_id:
            # Compatibilidad firma solicitada en Fase 1.5 sin romper llamadas existentes.
            return {"link": "", "requisition_id": str(requisition_id).strip()}
        if not empresa_id:
            raise ValueError("empresa_id es obligatorio para create_requisition")
        return await self._bank.create_requisition_link(
            empresa_id=empresa_id,
            institution_id=institution_id,
            redirect_url=redirect_url,
        )

    async def get_institutions(self, *, country_code: str = "ES") -> list[dict[str, Any]]:
        return await self._bank.get_institutions(country_code=country_code)

    async def get_transactions(
        self,
        *,
        requisition_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """Descarga movimientos en bruto para todas las cuentas de la requisición."""
        return await self._bank.get_transactions(
            requisition_id=requisition_id,
            date_from=date_from,
            date_to=date_to,
        )

    async def list_accounts(self, *, empresa_id: str) -> list[dict[str, Any]]:
        return await self._bank.list_accounts(empresa_id=empresa_id)

    async def fetch_transactions(
        self,
        *,
        empresa_id: str | None = None,
        requisition_id: str | None = None,
        days: int = 90,
    ) -> list[dict[str, Any]]:
        if requisition_id:
            return await self._bank.get_transactions(requisition_id=str(requisition_id).strip())
        if not empresa_id:
            raise ValueError("empresa_id o requisition_id es obligatorio")
        return await self._bank.fetch_transactions(empresa_id=empresa_id, days=days)

    async def complete_oauth_redirect(
        self,
        *,
        empresa_id: str,
        ref: str,
        days: int = 90,
    ) -> dict[str, Any]:
        return await self._bank.complete_oauth_redirect(empresa_id=empresa_id, ref=ref, days=days)

    async def sincronizar_y_conciliar(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> BankSyncResult:
        return await self._bank.sincronizar_y_conciliar(
            empresa_id=empresa_id, date_from=date_from, date_to=date_to
        )

    def underlying(self) -> BankService:
        """Acceso al servicio completo (cuentas, sync, match manual) sin duplicar lógica."""
        return self._bank
