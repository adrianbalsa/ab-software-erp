from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.plans import PLAN_ENTERPRISE, fetch_empresa_plan, normalize_plan
from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db.supabase import SupabaseAsync
from app.schemas.porte import PorteCreate, PorteOut
from app.services.eco_service import (
    calcular_huella_porte,
    factor_emision_huella_porte_default,
    peso_ton_desde_porte_create,
)
from app.services.maps_service import MapsService


class PortesService:
    def __init__(self, db: SupabaseAsync, maps: MapsService) -> None:
        self._db = db
        self._maps = maps

    async def list_portes_pendientes(self, *, empresa_id: str | UUID) -> list[PorteOut]:
        eid = str(empresa_id).strip()
        query = filter_not_deleted(
            self._db.table("portes")
            .select("*")
            .eq("empresa_id", eid)
            .eq("estado", "pendiente")
            .order("fecha", desc=False)
        )
        res: Any = await self._db.execute(query)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[PorteOut] = []
        for row in rows:
            try:
                out.append(PorteOut(**row))
            except Exception:
                continue
        return out

    async def create_porte(self, *, empresa_id: str | UUID, porte_in: PorteCreate) -> PorteOut:
        eid = str(empresa_id).strip()
        km_val = float(porte_in.km_estimados or 0.0)
        if km_val <= 0:
            km_val = float(await self._maps.get_distance_km(porte_in.origen, porte_in.destino))

        payload: dict[str, Any] = {
            "empresa_id": eid,
            "cliente_id": str(porte_in.cliente_id),
            "fecha": porte_in.fecha.isoformat(),
            "origen": porte_in.origen,
            "destino": porte_in.destino,
            "km_estimados": km_val,
            "bultos": porte_in.bultos,
            "descripcion": porte_in.descripcion,
            "precio_pactado": porte_in.precio_pactado,
            "estado": "pendiente",
        }
        if porte_in.peso_ton is not None:
            payload["peso_ton"] = float(porte_in.peso_ton)
        try:
            plan = await fetch_empresa_plan(self._db, empresa_id=eid)
            if normalize_plan(plan) == PLAN_ENTERPRISE:
                dist = float(km_val)
                peso = peso_ton_desde_porte_create(porte_in)
                fac = factor_emision_huella_porte_default()
                payload["co2_emitido"] = calcular_huella_porte(dist, peso, fac)
        except Exception:
            pass
        res: Any = await self._db.execute(self._db.table("portes").insert(payload))
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise RuntimeError("Supabase insert returned no rows")
        return PorteOut(**rows[0])

    async def get_porte(self, *, empresa_id: str | UUID, porte_id: str | UUID) -> PorteOut | None:
        """
        Un porte por id restringido a la empresa (equivalente a filtrar por ``empresa_id`` en RLS).
        """
        eid = str(empresa_id or "").strip()
        pid = str(porte_id or "").strip()
        if not eid or not pid:
            return None
        query = filter_not_deleted(
            self._db.table("portes").select("*").eq("empresa_id", eid).eq("id", pid).limit(1)
        )
        res: Any = await self._db.execute(query)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return None
        try:
            return PorteOut(**rows[0])
        except Exception:
            return None

    async def soft_delete_porte(self, *, empresa_id: str | UUID, porte_id: str | UUID) -> None:
        """Borrado lógico (no elimina fila; coherente con RLS y trazabilidad)."""
        eid = str(empresa_id or "").strip()
        pid = str(porte_id or "").strip()
        if not eid or not pid:
            raise ValueError("empresa_id y porte_id son obligatorios")
        await self._db.execute(
            self._db.table("portes")
            .update(soft_delete_payload())
            .eq("empresa_id", eid)
            .eq("id", pid)
            .is_("deleted_at", "null")
        )
