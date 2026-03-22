from __future__ import annotations

import logging
from typing import Any

from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db.supabase import SupabaseAsync
from app.schemas.admin_panel import (
    AuditoriaAdminRow,
    MetricasSaaSFacturacionOut,
    UsuarioAdminOut,
    UsuarioAdminPatch,
)
from app.schemas.empresa import EmpresaCreate, EmpresaOut, EmpresaUpdate

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def list_empresas(self) -> list[EmpresaOut]:
        q = filter_not_deleted(
            self._db.table("empresas")
            .select(
                "id, nif, nombre_legal, nombre_comercial, plan, activa, fecha_registro, email, telefono, direccion, deleted_at"
            )
            .order("fecha_registro", desc=True)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[EmpresaOut] = []
        for row in rows:
            try:
                out.append(EmpresaOut(**row))
            except Exception as exc:
                logger.warning(
                    "Fila empresas omitida (id=%s): %s",
                    row.get("id"),
                    exc,
                )
                continue
        return out

    async def create_empresa(self, *, empresa_in: EmpresaCreate) -> EmpresaOut:
        payload: dict[str, Any] = {
            "nif": empresa_in.nif.strip().upper(),
            "nombre_legal": empresa_in.nombre_legal.strip(),
            "nombre_comercial": (empresa_in.nombre_comercial or empresa_in.nombre_legal).strip(),
            "plan": empresa_in.plan,
            "email": empresa_in.email,
            "telefono": empresa_in.telefono,
            "direccion": empresa_in.direccion,
            "activa": bool(empresa_in.activa),
        }
        res: Any = await self._db.execute(self._db.table("empresas").insert(payload))
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise RuntimeError("Supabase insert empresa returned no rows")
        return EmpresaOut(**rows[0])

    async def update_empresa(self, *, empresa_id: str, patch: EmpresaUpdate) -> EmpresaOut:
        changes: dict[str, Any] = {}
        if patch.plan is not None:
            changes["plan"] = patch.plan
        if patch.activa is not None:
            changes["activa"] = patch.activa
        if patch.nombre_comercial is not None:
            changes["nombre_comercial"] = patch.nombre_comercial
        if patch.email is not None:
            changes["email"] = patch.email
        if patch.telefono is not None:
            changes["telefono"] = patch.telefono
        if patch.direccion is not None:
            changes["direccion"] = patch.direccion

        if not changes:
            # Fetch current
            res0: Any = await self._db.execute(
                self._db.table("empresas").select("*").eq("id", empresa_id).limit(1)
            )
            rows0: list[dict[str, Any]] = (res0.data or []) if hasattr(res0, "data") else []
            if not rows0:
                raise ValueError("Empresa no encontrada")
            return EmpresaOut(**rows0[0])

        res: Any = await self._db.execute(
            self._db.table("empresas").update(changes).eq("id", empresa_id)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            # Some policies return empty; re-fetch
            res2: Any = await self._db.execute(
                self._db.table("empresas").select("*").eq("id", empresa_id).limit(1)
            )
            rows2: list[dict[str, Any]] = (res2.data or []) if hasattr(res2, "data") else []
            if not rows2:
                raise ValueError("Empresa no encontrada")
            return EmpresaOut(**rows2[0])
        return EmpresaOut(**rows[0])

    async def soft_delete_empresa(self, *, empresa_id: str) -> None:
        """Archiva empresa (borrado lógico); no elimina la fila."""
        eid = str(empresa_id or "").strip()
        if not eid:
            raise ValueError("empresa_id inválido")
        await self._db.execute(
            self._db.table("empresas")
            .update(soft_delete_payload())
            .eq("id", eid)
            .is_("deleted_at", "null")
        )

    async def list_usuarios(self) -> list[UsuarioAdminOut]:
        q = self._db.table("usuarios").select("*").order("id", desc=True)
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[UsuarioAdminOut] = []
        for row in rows:
            try:
                r = dict(row)
                if "fecha_creacion" not in r and r.get("created_at") is not None:
                    r["fecha_creacion"] = str(r.get("created_at"))
                out.append(UsuarioAdminOut(**r))
            except Exception as exc:
                logger.warning("Fila usuario omitida (id=%s): %s", row.get("id"), exc)
                continue
        return out

    async def update_usuario(self, *, usuario_id: str, patch: UsuarioAdminPatch) -> UsuarioAdminOut:
        changes: dict[str, Any] = {}
        if patch.rol is not None:
            changes["rol"] = patch.rol
        if patch.activo is not None:
            changes["activo"] = patch.activo
        if not changes:
            res0: Any = await self._db.execute(
                self._db.table("usuarios").select("*").eq("id", usuario_id).limit(1)
            )
            rows0: list[dict[str, Any]] = (res0.data or []) if hasattr(res0, "data") else []
            if not rows0:
                raise ValueError("Usuario no encontrado")
            r = dict(rows0[0])
            if "fecha_creacion" not in r and r.get("created_at") is not None:
                r["fecha_creacion"] = str(r.get("created_at"))
            return UsuarioAdminOut(**r)

        res: Any = await self._db.execute(
            self._db.table("usuarios").update(changes).eq("id", usuario_id)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            res2: Any = await self._db.execute(
                self._db.table("usuarios").select("*").eq("id", usuario_id).limit(1)
            )
            rows2: list[dict[str, Any]] = (res2.data or []) if hasattr(res2, "data") else []
            if not rows2:
                raise ValueError("Usuario no encontrado")
            r = dict(rows2[0])
            if "fecha_creacion" not in r and r.get("created_at") is not None:
                r["fecha_creacion"] = str(r.get("created_at"))
            return UsuarioAdminOut(**r)
        r = dict(rows[0])
        if "fecha_creacion" not in r and r.get("created_at") is not None:
            r["fecha_creacion"] = str(r.get("created_at"))
        return UsuarioAdminOut(**r)

    async def list_auditoria(self, *, limit: int = 100) -> list[AuditoriaAdminRow]:
        lim = max(10, min(500, int(limit)))
        q = (
            self._db.table("auditoria")
            .select("*")
            .order("id", desc=True)
            .limit(lim)
        )
        res: Any = await self._db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[AuditoriaAdminRow] = []
        for row in rows:
            try:
                out.append(AuditoriaAdminRow(**row))
            except Exception:
                try:
                    out.append(AuditoriaAdminRow.model_validate(row))
                except Exception:
                    continue
        return out

    async def metricas_saas_facturacion(self) -> MetricasSaaSFacturacionOut:
        res: Any = await self._db.execute(
            self._db.table("facturas").select("total_factura, cuota_iva, fecha_emision")
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return MetricasSaaSFacturacionOut(
                total_bruto=0.0,
                total_iva=0.0,
                ingreso_neto=0.0,
                n_facturas=0,
                arpu=0.0,
            )
        total_bruto = sum(float(r.get("total_factura") or 0.0) for r in rows)
        total_iva = sum(float(r.get("cuota_iva") or 0.0) for r in rows)
        ingreso_neto = total_bruto - total_iva
        n = len(rows)
        arpu = ingreso_neto / n if n else 0.0
        return MetricasSaaSFacturacionOut(
            total_bruto=total_bruto,
            total_iva=total_iva,
            ingreso_neto=ingreso_neto,
            n_facturas=n,
            arpu=arpu,
        )

