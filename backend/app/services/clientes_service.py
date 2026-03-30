from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db import supabase as supabase_db
from app.db.supabase import SupabaseAsync
from app.schemas.cliente import ClienteCreate, ClienteOut
from app.core.crypto import pii_crypto
from app.services import email_service


def _eid(empresa_id: str | UUID) -> str:
    eid = str(empresa_id).strip()
    if not eid:
        raise ValueError("empresa_id es obligatorio")
    return eid


class ClientesService:
    """CRUD maestro `clientes` con borrado lógico (D2/D3)."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_clientes(self, *, empresa_id: str | UUID) -> list[ClienteOut]:
        eid = _eid(empresa_id)
        q = filter_not_deleted(
            self._db.table("clientes").select("*").eq("empresa_id", eid).order("nombre", desc=False)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[ClienteOut] = []
        for row in rows:
            try:
                rn = dict(row)
                raw_nif = rn.get("nif")
                if isinstance(raw_nif, str) and raw_nif.strip():
                    rn["nif"] = pii_crypto.decrypt_pii(raw_nif) or raw_nif
                out.append(ClienteOut(**rn))
            except Exception:
                continue
        return out

    async def get_cliente(self, *, empresa_id: str | UUID, cliente_id: UUID) -> ClienteOut | None:
        eid = _eid(empresa_id)
        cid = str(cliente_id)
        q = filter_not_deleted(
            self._db.table("clientes").select("*").eq("empresa_id", eid).eq("id", cid).limit(1)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return None
        rn = dict(rows[0])
        raw_nif = rn.get("nif")
        if isinstance(raw_nif, str) and raw_nif.strip():
            rn["nif"] = pii_crypto.decrypt_pii(raw_nif) or raw_nif
        return ClienteOut(**rn)

    async def get_cliente_by_id(self, *, cliente_id: str, empresa_id: str) -> Any | None:
        """Alias pragmático para tests/unit y servicios de onboarding."""
        q = filter_not_deleted(
            self._db.table("clientes")
            .select("id,empresa_id,email,fecha_invitacion,riesgo_aceptado,mandato_activo")
            .eq("id", str(cliente_id).strip())
            .eq("empresa_id", str(empresa_id).strip())
            .limit(1)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return rows[0] if rows else None

    async def resend_onboarding_invite(
        self,
        *,
        cliente_id: str,
        empresa_id: str,
    ) -> dict[str, str]:
        cliente = await self.get_cliente_by_id(cliente_id=cliente_id, empresa_id=empresa_id)
        if cliente is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

        riesgo_aceptado = bool(
            getattr(cliente, "riesgo_aceptado", False)
            if not isinstance(cliente, dict)
            else cliente.get("riesgo_aceptado")
        )
        mandato_activo = bool(
            getattr(cliente, "mandato_activo", False)
            if not isinstance(cliente, dict)
            else cliente.get("mandato_activo")
        )
        if riesgo_aceptado or mandato_activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El cliente ya completó el onboarding",
            )

        email_raw = (
            getattr(cliente, "email", None) if not isinstance(cliente, dict) else cliente.get("email")
        )
        email = str(email_raw or "").strip().lower()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El cliente no tiene un email válido",
            )

        magic_link = await supabase_db.auth_admin_generate_link(
            email=email,
            metadata={
                "empresa_id": str(empresa_id).strip(),
                "cliente_id": str(cliente_id).strip(),
                "rbac_role": "cliente",
            },
        )

        email_sent = email_service.send_onboarding_invite(email, magic_link)
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo enviar la invitación de onboarding",
            )

        # Best-effort: no bloquea reenvío si falla por compatibilidad de esquema.
        try:
            await self._db.execute(
                self._db.table("audit_logs").insert(
                    {
                        "empresa_id": str(empresa_id).strip(),
                        "table_name": "clientes",
                        "record_id": str(cliente_id).strip(),
                        "action": "INVITE_RESENT",
                        "old_data": {},
                        "new_data": {"invite_email": email, "invite_channel": "resend_email"},
                    }
                )
            )
        except Exception:
            pass

        return {"message": "Invitación reenviada correctamente"}

    async def create_cliente(self, *, empresa_id: str | UUID, payload: ClienteCreate) -> ClienteOut:
        eid = _eid(empresa_id)
        body: dict[str, Any] = {
            "empresa_id": eid,
            "nombre": payload.nombre.strip(),
            "nif": pii_crypto.encrypt_pii((payload.nif or "").strip()) if payload.nif else None,
            "email": payload.email,
            "telefono": payload.telefono,
            "direccion": payload.direccion,
        }
        res: Any = await self._db.execute(self._db.table("clientes").insert(body))
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise RuntimeError("Supabase insert clientes returned no rows")
        rn = dict(rows[0])
        raw_nif = rn.get("nif")
        if isinstance(raw_nif, str) and raw_nif.strip():
            rn["nif"] = pii_crypto.decrypt_pii(raw_nif) or raw_nif
        return ClienteOut(**rn)

    async def soft_delete_cliente(self, *, empresa_id: str | UUID, cliente_id: UUID) -> None:
        eid = _eid(empresa_id)
        cid = str(cliente_id)
        await self._db.execute(
            self._db.table("clientes")
            .update(soft_delete_payload())
            .eq("empresa_id", eid)
            .eq("id", cid)
            .is_("deleted_at", "null")
        )
