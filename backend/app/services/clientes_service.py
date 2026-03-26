from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db.supabase import SupabaseAsync
from app.schemas.cliente import ClienteCreate, ClienteOut
from app.core.crypto import pii_crypto


def _eid(empresa_id: str | UUID) -> str:
    return str(empresa_id).strip()


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
