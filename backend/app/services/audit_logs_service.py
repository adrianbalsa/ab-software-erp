from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from app.db.supabase import SupabaseAsync
from app.schemas.audit_log import AuditLogOut

_EMAIL_RE = re.compile(r"(?P<local>[A-Z0-9._%+-]+)@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
_NIF_RE = re.compile(
    r"\b(?:\d{8}[A-HJ-NP-TV-Z]|[XYZ]\d{7}[A-HJ-NP-TV-Z]|[A-HJ-NP-SUVW][0-9]{7}[0-9A-J])\b",
    re.IGNORECASE,
)
_SENSITIVE_KEY_FRAGMENTS = (
    "email",
    "correo",
    "mail",
    "nif",
    "dni",
    "cif",
    "nie",
    "phone",
    "telefono",
    "movil",
    "iban",
    "direccion",
    "address",
    "name",
    "nombre",
    "apellidos",
    "full_name",
    "actor",
)


def _pii_hash(value: str) -> str:
    normalized = " ".join(str(value or "").strip().split()).lower()
    return hashlib.sha256(f"audit-log-pii:v1:{normalized}".encode("utf-8")).hexdigest()


def _mask_email(value: str) -> str:
    raw = str(value or "").strip()
    match = _EMAIL_RE.fullmatch(raw)
    if not match:
        return f"[email_sha256:{_pii_hash(raw)[:16]}]"
    local = match.group("local")
    domain = match.group("domain").lower()
    if len(local) <= 2:
        masked_local = f"{local[:1]}***"
    else:
        masked_local = f"{local[:1]}***{local[-1:]}"
    return f"{masked_local}@{domain}#sha256:{_pii_hash(raw)[:16]}"


def _mask_nif(value: str) -> str:
    raw = str(value or "").strip().upper()
    if len(raw) <= 4:
        masked = "***"
    else:
        masked = f"{raw[:1]}***{raw[-2:]}"
    return f"{masked}#sha256:{_pii_hash(raw)[:16]}"


def _mask_person_name(value: str) -> str:
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        return value
    compact = raw.replace(" ", "")
    if len(compact) <= 2:
        masked = f"{compact[:1]}***" if compact else "***"
    else:
        masked = f"{compact[:1]}***{compact[-3:]}"
    return f"{masked}#sha256:{_pii_hash(raw)[:16]}"


def _key_looks_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _pseudonymize_scalar(value: Any, *, force: bool = False) -> Any:
    if not isinstance(value, str):
        if force and value is not None and not isinstance(value, bool):
            return f"[pii_sha256:{_pii_hash(str(value))[:16]}]"
        return value
    raw = value.strip()
    if not raw:
        return value
    if force:
        if _EMAIL_RE.fullmatch(raw):
            return _mask_email(raw)
        if _NIF_RE.fullmatch(raw):
            return _mask_nif(raw)
        if "@" not in raw and any(ch.isalpha() for ch in raw):
            return _mask_person_name(raw)
        return f"[pii_sha256:{_pii_hash(raw)[:16]}]"
    masked = _EMAIL_RE.sub(lambda m: _mask_email(m.group(0)), value)
    return _NIF_RE.sub(lambda m: _mask_nif(m.group(0)), masked)


def _pseudonymize_audit_payload(value: Any, *, depth: int = 0, force: bool = False) -> Any:
    if depth > 12:
        return "[Truncated]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            out[key_str] = _pseudonymize_audit_payload(
                item,
                depth=depth + 1,
                force=force or _key_looks_sensitive(key_str),
            )
        return out
    if isinstance(value, list):
        return [
            _pseudonymize_audit_payload(item, depth=depth + 1, force=force)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _pseudonymize_audit_payload(item, depth=depth + 1, force=force)
            for item in value
        ]
    return _pseudonymize_scalar(value, force=force)


def pseudonymize_audit_payload(value: Any) -> Any:
    """
    Pseudonimiza un payload antes de persistirlo en ``audit_logs`` cuando el insert
    no pasa por ``AuditLogsService`` (p. ej. RPC sync desde scripts).
    """
    return _pseudonymize_audit_payload(value)


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
                params["p_old_data"] = _pseudonymize_audit_payload(old_value)
            if new_value is not None:
                params["p_new_data"] = _pseudonymize_audit_payload(new_value)
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

    async def log_bank_reconciliation(
        self,
        *,
        empresa_id: str | UUID,
        transaction_id: str,
        factura_id: int,
        user_id: str | UUID | None = None,
    ) -> None:
        """Trazabilidad de conciliación bancaria (auto o manual), alineada con auditoría de API."""
        await self.log_sensitive_action(
            empresa_id=empresa_id,
            table_name="bank_reconciliation",
            record_id=str(transaction_id).strip(),
            action="UPDATE",
            new_value={
                "transaction_id": str(transaction_id).strip(),
                "factura_id": int(factura_id),
                "estado_factura": "cobrada",
                "source": "reconciliation",
            },
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
