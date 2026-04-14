from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.supabase import SupabaseAsync
from app.schemas.audit_log import AuditLogOut


class AuditLogsService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_for_empresa(
        self,
        *,
        empresa_id: str,
        limit: int = 100,
        table_name: str | None = None,
        record_id: str | None = None,
        ascending: bool = False,
    ) -> list[AuditLogOut]:
        eid = str(empresa_id or "").strip()
        if not eid:
            return []
        lim = max(1, min(int(limit), 500))
        q: Any = (
            self._db.table("audit_logs")
            .select("*")
            .eq("empresa_id", eid)
            .order("created_at", desc=not ascending)
        )
        if table_name and str(table_name).strip():
            q = q.eq("table_name", str(table_name).strip())
        if record_id and str(record_id).strip():
            q = q.eq("record_id", str(record_id).strip())
        q = q.limit(lim)
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[AuditLogOut] = []
        for row in rows:
            try:
                out.append(AuditLogOut.model_validate(row))
            except Exception:
                continue
        return out

    async def log_sensitive_action(
        self,
        *,
        empresa_id: str | UUID,
        table_name: str,
        record_id: str,
        action: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        user_id: str | UUID | None = None,
    ) -> None:
        """
        Registra una acción sensible en la tabla audit_logs.

        Args:
            empresa_id: ID de la empresa
            table_name: Nombre de la tabla afectada
            record_id: ID del registro afectado
            action: Acción realizada (INSERT, UPDATE, DELETE, CUSTOM)
            old_value: Valor anterior del registro (para UPDATE/DELETE)
            new_value: Valor nuevo del registro (para INSERT/UPDATE)
            user_id: ID del usuario que realizó la acción

        Example:
            await audit_service.log_sensitive_action(
                empresa_id=empresa_id,
                table_name="vehiculos",
                record_id=vehiculo_id,
                action="DELETE",
                old_value={"matricula": "ABC123", "estado": "activo"},
                user_id=current_user.usuario_id,
            )
        """
        try:
            params: dict[str, Any] = {
                "p_empresa_id": str(empresa_id).strip(),
                "p_table_name": str(table_name).strip(),
                "p_record_id": str(record_id).strip(),
                "p_action": str(action).strip().upper(),
            }
            if old_value is not None:
                params["p_old_data"] = old_value
            if new_value is not None:
                params["p_new_data"] = new_value
            if user_id:
                params["p_changed_by"] = str(user_id).strip()
            await self._db.rpc("audit_logs_insert_api_event", params)
        except Exception as e:
            # No fallar la operación principal si falla el audit log
            # Solo registrar el error para investigación
            import logging
            logging.getLogger(__name__).warning(
                f"Error al registrar audit log: {e}",
                exc_info=True,
            )

    async def log_vehiculo_deletion(
        self,
        *,
        empresa_id: str | UUID,
        vehiculo_id: str | UUID,
        vehiculo_data: dict[str, Any],
        user_id: str | UUID | None = None,
    ) -> None:
        """Helper específico para registrar eliminación de vehículos."""
        await self.log_sensitive_action(
            empresa_id=empresa_id,
            table_name="flota",
            record_id=str(vehiculo_id),
            action="DELETE",
            old_value=vehiculo_data,
            user_id=user_id,
        )

    async def log_precio_porte_change(
        self,
        *,
        empresa_id: str | UUID,
        porte_id: str | UUID,
        old_precio: float,
        new_precio: float,
        user_id: str | UUID | None = None,
    ) -> None:
        """Helper específico para registrar cambio de precio en portes."""
        await self.log_sensitive_action(
            empresa_id=empresa_id,
            table_name="portes",
            record_id=str(porte_id),
            action="UPDATE",
            old_value={"precio_pactado": old_precio},
            new_value={"precio_pactado": new_precio},
            user_id=user_id,
        )

    async def log_factura_modification(
        self,
        *,
        empresa_id: str | UUID,
        factura_id: str | UUID,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        user_id: str | UUID | None = None,
    ) -> None:
        """Helper específico para registrar modificaciones en facturas."""
        await self.log_sensitive_action(
            empresa_id=empresa_id,
            table_name="facturas",
            record_id=str(factura_id),
            action="UPDATE",
            old_value=old_data,
            new_value=new_data,
            user_id=user_id,
        )

    async def log_cliente_data_change(
        self,
        *,
        empresa_id: str | UUID,
        cliente_id: str | UUID,
        action: str,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
        user_id: str | UUID | None = None,
    ) -> None:
        """Helper específico para registrar cambios en datos de clientes."""
        await self.log_sensitive_action(
            empresa_id=empresa_id,
            table_name="clientes",
            record_id=str(cliente_id),
            action=action,
            old_value=old_data,
            new_value=new_data,
            user_id=user_id,
        )
