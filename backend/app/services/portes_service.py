from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.math_engine import as_float_fiat, round_fiat, safe_divide, to_decimal
from app.core.esg_engine import calculate_co2_emissions, resolve_normativa_euro_for_co2
from app.core.plans import PLAN_ENTERPRISE, fetch_empresa_plan, normalize_plan
from app.db.soft_delete import filter_not_deleted, soft_delete_payload
from app.db.supabase import SupabaseAsync
from app.schemas.cmr import (
    CmrDataOut,
    CmrLugarFecha,
    CmrMercanciaBlock,
    CmrPartyBlock,
)
from app.schemas.porte import PorteCreate, PorteOut
from app.schemas.user import UserOut
from app.services.pdf_service import generar_albaran_entrega_pdf
from app.services.eco_service import (
    calcular_huella_porte,
    factor_emision_huella_porte_default,
    peso_ton_desde_porte_create,
    peso_ton_desde_porte_row,
)
from app.services.finance_pending import aggregate_pending_and_trend
from app.services.maps_service import MapsService

_log = logging.getLogger(__name__)


class PorteDomainError(ValueError):
    """Error de reglas de negocio de Portes."""


class PortesService:
    def __init__(self, db: SupabaseAsync, maps: MapsService) -> None:
        self._db = db
        self._maps = maps

    async def _normativa_euro_co2_para_vehiculo(
        self, *, empresa_id: str, vehiculo_flota_id: str | None
    ) -> str:
        """Lee ``normativa_euro`` (y fallback ``certificacion_emisiones``) desde ``flota``."""
        vid = str(vehiculo_flota_id or "").strip()
        if not vid:
            return resolve_normativa_euro_for_co2()
        try:
            res: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select("normativa_euro,certificacion_emisiones")
                    .eq("empresa_id", str(empresa_id).strip())
                    .eq("id", vid)
                    .limit(1)
                )
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        except Exception:
            return resolve_normativa_euro_for_co2()
        if not rows:
            return resolve_normativa_euro_for_co2()
        r0 = rows[0]
        return resolve_normativa_euro_for_co2(
            normativa_euro=r0.get("normativa_euro"),
            certificacion_emisiones=r0.get("certificacion_emisiones"),
        )

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

    async def list_portes_entregados_cliente(
        self,
        *,
        empresa_id: str | UUID,
        cliente_id: str | UUID,
    ) -> list[dict[str, Any]]:
        """Portes en estado Entregado para un cargador (portal cliente)."""
        eid = str(empresa_id).strip()
        cid = str(cliente_id).strip()
        if not eid or not cid:
            return []
        query = filter_not_deleted(
            self._db.table("portes")
            .select("id,origen,destino,fecha,fecha_entrega_real,estado,cliente_id")
            .eq("empresa_id", eid)
            .eq("cliente_id", cid)
            .eq("estado", "Entregado")
            .order("fecha_entrega_real", desc=True)
        )
        res: Any = await self._db.execute(query)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        return [dict(r) for r in rows]

    async def create_porte(
        self,
        *,
        empresa_id: str | UUID,
        porte_in: PorteCreate,
        caller_is_owner: bool = False,
    ) -> PorteOut:
        eid = str(empresa_id).strip()
        if not eid:
            raise PorteDomainError("empresa_id es obligatorio")
        cid = str(porte_in.cliente_id).strip()
        if not cid:
            raise PorteDomainError("cliente_id es obligatorio")

        # Bloqueo de crédito comercial: sin onboarding de riesgo no se permite operar.
        res_cli: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("clientes")
                .select("id,riesgo_aceptado,limite_credito")
                .eq("empresa_id", eid)
                .eq("id", cid)
                .limit(1)
            )
        )
        cli_rows: list[dict[str, Any]] = (res_cli.data or []) if hasattr(res_cli, "data") else []
        if not cli_rows:
            raise PorteDomainError("Cliente no encontrado")
        cli_row = cli_rows[0]
        riesgo_aceptado = cli_row.get("riesgo_aceptado")
        if riesgo_aceptado is not True:
            raise PorteDomainError(
                "Operación denegada: El cliente no ha aceptado las condiciones de riesgo comercial (Onboarding incompleto)."
            )

        if not caller_is_owner:
            try:
                limite_raw = cli_row.get("limite_credito")
                limite_credito = max(0.0, float(limite_raw if limite_raw is not None else 0.0))
            except (TypeError, ValueError):
                limite_credito = 0.0
            pending_by_client, _, _ = await aggregate_pending_and_trend(
                self._db, eid, months_for_trend=None
            )
            saldo = max(0.0, float(pending_by_client.get(cid, 0.0)))
            try:
                nuevo = max(0.0, float(porte_in.precio_pactado))
            except (TypeError, ValueError):
                nuevo = 0.0
            if saldo + nuevo > limite_credito:
                raise PorteDomainError(
                    "Límite de crédito excedido. No se pueden asignar más portes a este cliente."
                )

        km_val = float(porte_in.km_estimados or 0.0)
        if km_val <= 0:
            km_val = float(
                await self._maps.get_distance_km(
                    porte_in.origen,
                    porte_in.destino,
                    tenant_empresa_id=eid,
                )
            )

        vid_create = str(porte_in.vehiculo_id).strip() if porte_in.vehiculo_id else ""
        if vid_create:
            res_v: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select("id")
                    .eq("empresa_id", eid)
                    .eq("id", vid_create)
                    .limit(1)
                )
            )
            vrows: list[dict[str, Any]] = (res_v.data or []) if hasattr(res_v, "data") else []
            if not vrows:
                raise PorteDomainError("El vehículo indicado no existe en la flota de la empresa.")

        euro_co2 = await self._normativa_euro_co2_para_vehiculo(
            empresa_id=eid,
            vehiculo_flota_id=vid_create or None,
        )

        payload: dict[str, Any] = {
            "empresa_id": eid,
            "cliente_id": cid,
            "fecha": porte_in.fecha.isoformat(),
            "origen": porte_in.origen,
            "destino": porte_in.destino,
            "km_estimados": km_val,
            "bultos": porte_in.bultos,
            "descripcion": porte_in.descripcion,
            "precio_pactado": porte_in.precio_pactado,
            "estado": "pendiente",
            # Huella simplificada para cuadro financiero ESG (factor por normativa EURO del vehículo).
            "co2_kg": calculate_co2_emissions(km_val, euro_co2),
        }
        if vid_create:
            payload["vehiculo_id"] = vid_create
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

    @staticmethod
    def _ingreso_neto_sin_iva(row: dict[str, Any]) -> Decimal:
        base = row.get("base_imponible")
        if base is not None:
            return round_fiat(base)
        total = round_fiat(row.get("total_factura") or 0)
        cuota = round_fiat(row.get("cuota_iva") or 0)
        net = round_fiat(total - cuota)
        return net if net > 0 else Decimal("0.00")

    @staticmethod
    def _gasto_neto_sin_iva(row: dict[str, Any]) -> Decimal:
        gross = round_fiat(row.get("total_eur") or row.get("total_chf") or 0)
        iva_raw = row.get("iva")
        if iva_raw is None:
            return gross if gross > 0 else Decimal("0.00")
        try:
            iva = round_fiat(iva_raw)
        except Exception:
            return gross if gross > 0 else Decimal("0.00")
        net = round_fiat(gross - max(Decimal("0.00"), iva))
        return net if net > 0 else Decimal("0.00")

    async def _current_margin_and_cost_per_km(self, *, empresa_id: str) -> tuple[float, float]:
        """
        Retorna (margen_km_eur, coste_km_eur) para proyección.

        Prioridad:
        1) `public.portes_activos` para `margen_km_eur`.
        2) Fallback cálculo financiero histórico por facturas/gastos.
        """
        eid = str(empresa_id or "").strip()
        margen_km = 0.0
        coste_km = 0.0

        try:
            res_view: Any = await self._db.execute(
                self._db.table("portes_activos").select("margen_km_eur").eq("empresa_id", eid)
            )
            rows_view: list[dict[str, Any]] = (res_view.data or []) if hasattr(res_view, "data") else []
            vals = [float(r.get("margen_km_eur") or 0.0) for r in rows_view]
            if vals:
                s = sum(to_decimal(v) for v in vals)
                margen_km = float(round_fiat(s / to_decimal(len(vals))))
        except Exception:
            margen_km = 0.0

        res_fac: Any = await self._db.execute(
            self._db.table("facturas")
            .select("base_imponible,total_factura,cuota_iva,total_km_estimados_snapshot")
            .eq("empresa_id", eid)
        )
        fact_rows: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []
        acc_km = Decimal("0")
        for r in fact_rows:
            acc_km += to_decimal(r.get("total_km_estimados_snapshot") or 0)
        km_total = round_fiat(acc_km)

        acc_in = Decimal("0")
        for r in fact_rows:
            acc_in += self._ingreso_neto_sin_iva(r)
        ingresos = round_fiat(acc_in)

        res_gas: Any = await self._db.execute(
            filter_not_deleted(self._db.table("gastos").select("*").eq("empresa_id", eid))
        )
        gas_rows: list[dict[str, Any]] = (res_gas.data or []) if hasattr(res_gas, "data") else []
        acc_gas = Decimal("0")
        for r in gas_rows:
            acc_gas += self._gasto_neto_sin_iva(r)
        gastos = round_fiat(acc_gas)

        coste_km = 0.0
        if km_total > 0:
            margen_fin_km = safe_divide(ingresos - gastos, km_total)
            coste_km = float(safe_divide(gastos, km_total))
            if abs(margen_km) < 1e-9:
                margen_km = float(margen_fin_km)

        return float(margen_km), float(coste_km)

    async def operational_cost_per_km_eur(self, *, empresa_id: str, default: float = 1.10) -> float:
        """
        Coste operativo €/km de la empresa (histórico facturas/gastos vía ``_current_margin_and_cost_per_km``).
        Si el coste es nulo o ≤ 0, devuelve ``default`` (p. ej. 1.10 €/km).
        """
        _, coste_km = await self._current_margin_and_cost_per_km(empresa_id=str(empresa_id))
        if coste_km is None or float(coste_km) <= 0.0:
            return float(default)
        return float(coste_km)

    async def cotizar_porte(
        self,
        *,
        empresa_id: str | UUID,
        origen: str,
        destino: str,
        precio_oferta: float = 0.0,
        km_estimados: float | None = None,
        waypoints: list[str] | None = None,
    ) -> dict[str, Any]:
        eid = str(empresa_id or "").strip()
        km_manual = km_estimados is not None and float(km_estimados) > 0
        tiene_peajes: bool | None = None
        distancia_desde_google_directions = False

        if km_manual:
            km = float(km_estimados or 0.0)
            tiempo_min = MapsService._estimate_duration_minutes(km)
        else:
            ruta = await self._maps.calcular_ruta_optima(origen, destino, waypoints)
            km = float(ruta["distancia_km"])
            tiempo_min = int(ruta["tiempo_estimado_min"])
            tiene_peajes = bool(ruta.get("tiene_peajes"))
            distancia_desde_google_directions = True

        margen_km, coste_km = await self._current_margin_and_cost_per_km(empresa_id=eid)
        km_dec = round_fiat(km)
        coste_op_dec = round_fiat(km_dec * to_decimal(coste_km))
        coste_operativo = float(coste_op_dec)

        precio_sugerido: float | None = None
        if precio_oferta > 0:
            po = round_fiat(precio_oferta)
            margen_proyectado = float(round_fiat(po - coste_op_dec))
            es_rentable = margen_proyectado > 0
        else:
            margen_proyectado = float(round_fiat(km_dec * to_decimal(margen_km)))
            precio_sugerido = float(round_fiat(coste_op_dec + km_dec * to_decimal(margen_km)))
            es_rentable = None

        return {
            "kilometros_totales": as_float_fiat(km_dec),
            "tiempo_estimado_min": int(max(0, tiempo_min)),
            "coste_operativo_estimado": coste_operativo,
            "margen_proyectado": margen_proyectado,
            "es_rentable": es_rentable,
            "tiene_peajes": tiene_peajes,
            "precio_sugerido": precio_sugerido,
            "distancia_desde_google_directions": distancia_desde_google_directions,
        }

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

    async def get_cmr_data(self, *, empresa_id: str | UUID, porte_id: str | UUID) -> CmrDataOut | None:
        """
        Agrega empresa, cliente, vehículo (flota) y porte para documento CMR.
        ``conductor_nombre`` opcional en fila porte (migración); sin vehículo/conductor, campos null.
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
        pr = rows[0]

        res_e: Any = await self._db.execute(
            self._db.table("empresas").select("*").eq("id", eid).limit(1)
        )
        erows: list[dict[str, Any]] = (res_e.data or []) if hasattr(res_e, "data") else []
        emp = erows[0] if erows else {}

        cid = str(pr.get("cliente_id") or pr.get("cliente") or "").strip()
        cli: dict[str, Any] = {}
        if cid:
            res_c: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("clientes").select("*").eq("empresa_id", eid).eq("id", cid).limit(1)
                )
            )
            crows = (res_c.data or []) if hasattr(res_c, "data") else []
            if crows:
                cli = crows[0]

        vid = str(pr.get("vehiculo_id") or "").strip()
        flota_row: dict[str, Any] = {}
        if vid:
            res_f: Any = await self._db.execute(
                filter_not_deleted(
                    self._db.table("flota")
                    .select("matricula, vehiculo")
                    .eq("empresa_id", eid)
                    .eq("id", vid)
                    .limit(1)
                )
            )
            frows = (res_f.data or []) if hasattr(res_f, "data") else []
            if frows:
                flota_row = frows[0]

        def _d(val: Any) -> date | None:
            if val is None:
                return None
            if isinstance(val, date):
                return val
            if isinstance(val, str) and val:
                try:
                    return date.fromisoformat(val[:10])
                except ValueError:
                    return None
            return None

        fecha_p = _d(pr.get("fecha")) or date.today()
        origen = str(pr.get("origen") or "").strip()
        destino = str(pr.get("destino") or "").strip()

        nif_cli = cli.get("nif")
        remitente = CmrPartyBlock(
            nombre=str(cli.get("nombre") or "").strip() or None,
            nif=str(nif_cli).strip() if nif_cli not in (None, "") else None,
            direccion=str(cli.get("direccion") or "").strip() or None,
            pais=None,
        )
        consignatario = CmrPartyBlock(
            nombre=None,
            nif=None,
            direccion=destino or None,
            pais=None,
        )
        transportista = CmrPartyBlock(
            nombre=str(emp.get("nombre_comercial") or emp.get("nombre_legal") or "").strip() or None,
            nif=str(emp.get("nif") or "").strip() or None,
            direccion=str(emp.get("direccion") or "").strip() or None,
            pais=None,
        )

        peso_ton = pr.get("peso_ton")
        try:
            pt = float(peso_ton) if peso_ton is not None else None
        except (TypeError, ValueError):
            pt = None
        peso_kg = round(pt * 1000.0, 3) if pt is not None and pt > 0 else None

        matricula = str(flota_row.get("matricula") or "").strip() or None
        nombre_veh = str(flota_row.get("vehiculo") or "").strip() or None
        conductor = pr.get("conductor_nombre")
        conductor_s = str(conductor).strip() if conductor is not None else ""
        conductor_nom = conductor_s or None

        try:
            bultos = int(pr.get("bultos") or 0)
        except (TypeError, ValueError):
            bultos = 0

        mercancia = CmrMercanciaBlock(
            descripcion=str(pr.get("descripcion") or "").strip() or None,
            bultos=bultos if bultos > 0 else None,
            peso_kg=peso_kg,
            peso_ton=pt,
            volumen_m3=None,
            matricula_vehiculo=matricula,
            nombre_vehiculo=nombre_veh,
            nombre_conductor=conductor_nom,
        )

        return CmrDataOut(
            porte_id=UUID(str(pr["id"])),
            fecha=fecha_p,
            km_estimados=float(pr.get("km_estimados") or 0) or None,
            casilla_1_remitente=remitente,
            casilla_2_consignatario=consignatario,
            casilla_3_lugar_entrega_mercancia=destino or None,
            casilla_4_lugar_fecha_toma_carga=CmrLugarFecha(lugar=origen or None, fecha=fecha_p),
            casilla_6_12_mercancia=mercancia,
            casilla_16_transportista=transportista,
            meta={"cmr_version": "1", "origen_texto": origen, "destino_texto": destino},
        )

    @staticmethod
    def _normalize_firma_b64(raw: str) -> str:
        s = str(raw or "").strip()
        if s.startswith("data:") and "," in s:
            return s.split(",", 1)[1].strip()
        return s

    @staticmethod
    def _puede_conductor_firmar_porte(user: UserOut, row: dict[str, Any]) -> bool:
        if user.rbac_role != "driver":
            return True
        vid_u = user.assigned_vehiculo_id
        pv = row.get("vehiculo_id")
        if pv and vid_u and str(pv).strip() == str(vid_u).strip():
            return True
        cuid = row.get("conductor_asignado_id")
        if cuid and user.usuario_id and str(cuid).strip() == str(user.usuario_id).strip():
            return True
        return False

    async def firmar_entrega(
        self,
        *,
        empresa_id: str | UUID,
        porte_id: str | UUID,
        current_user: UserOut,
        firma_b64: str,
        nombre_consignatario: str,
        dni_consignatario: str | None = None,
    ) -> dict[str, Any]:
        """
        Registra firma POD y marca ``estado='Entregado'``.
        Conductores: vehículo asignado = vehículo del porte, o ``conductor_asignado_id`` = perfil.
        """
        eid = str(empresa_id or "").strip()
        pid = str(porte_id or "").strip()
        if not eid or not pid:
            raise ValueError("empresa_id y porte_id son obligatorios")

        query = filter_not_deleted(
            self._db.table("portes").select("*").eq("empresa_id", eid).eq("id", pid).limit(1)
        )
        res: Any = await self._db.execute(query)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Porte no encontrado")
        row = rows[0]

        if not self._puede_conductor_firmar_porte(current_user, row):
            raise PermissionError("No tiene permiso para firmar este porte")

        est = str(row.get("estado") or "").strip()
        if est == "facturado":
            raise ValueError("El porte ya está facturado; no se puede modificar la entrega")
        if est.lower() == "entregado":
            raise ValueError("La entrega ya estaba registrada")

        b64 = self._normalize_firma_b64(firma_b64)
        if len(b64) < 20:
            raise ValueError("Firma inválida o demasiado corta")

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        vid_raw = row.get("vehiculo_id")
        km_trip = round_fiat(to_decimal(row.get("km_estimados") or 0))
        euro_entrega = await self._normativa_euro_co2_para_vehiculo(
            empresa_id=eid,
            vehiculo_flota_id=str(vid_raw).strip() if vid_raw else None,
        )
        km_float = float(km_trip) if km_trip > 0 else 0.0

        payload: dict[str, Any] = {
            "firma_consignatario_b64": b64,
            "nombre_consignatario_final": nombre_consignatario.strip()[:255],
            "fecha_entrega_real": now_iso,
            "estado": "Entregado",
            "co2_kg": calculate_co2_emissions(km_float, euro_entrega),
        }
        try:
            plan_e = await fetch_empresa_plan(self._db, empresa_id=eid)
            if normalize_plan(plan_e) == PLAN_ENTERPRISE and km_float > 0:
                peso_e = peso_ton_desde_porte_row(dict(row))
                fac_e = factor_emision_huella_porte_default()
                payload["co2_emitido"] = calcular_huella_porte(km_float, peso_e, fac_e)
        except Exception:
            pass
        dni = (dni_consignatario or "").strip()
        if dni:
            payload["dni_consignatario"] = dni[:32]

        await self._db.execute(
            self._db.table("portes").update(payload).eq("empresa_id", eid).eq("id", pid)
        )
        odometro_actualizado = False
        odometro_error: str | None = None
        if vid_raw and km_trip > 0:
            try:
                await self._db.rpc(
                    "increment_vehiculo_odometro",
                    {
                        "p_empresa_id": str(eid),
                        "p_vehiculo_id": str(vid_raw).strip(),
                        # Se envía como cadena decimal para evitar drift binario.
                        "p_km": str(km_trip),
                    },
                )
                odometro_actualizado = True
            except Exception as exc:
                odometro_error = str(exc)
                _log.warning(
                    "increment_vehiculo_odometro falló (porte=%s vehiculo=%s): %s",
                    pid,
                    vid_raw,
                    exc,
                )

        return {
            "porte_id": pid,
            "estado": "Entregado",
            "fecha_entrega_real": now,
            "odometro_actualizado": odometro_actualizado,
            "odometro_error": odometro_error,
        }

    async def get_albaran_entrega_pdf(self, *, empresa_id: str | UUID, porte_id: str | UUID) -> bytes:
        """PDF POD con firma; requiere entrega firmada."""
        eid = str(empresa_id or "").strip()
        pid = str(porte_id or "").strip()
        if not eid or not pid:
            raise ValueError("empresa_id y porte_id son obligatorios")

        query = filter_not_deleted(
            self._db.table("portes").select("*").eq("empresa_id", eid).eq("id", pid).limit(1)
        )
        res: Any = await self._db.execute(query)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise ValueError("Porte no encontrado")
        pr = rows[0]
        firma = pr.get("firma_consignatario_b64")
        if not firma or not str(firma).strip():
            raise ValueError("No hay firma de entrega registrada para este porte")

        res_e: Any = await self._db.execute(
            self._db.table("empresas").select("*").eq("id", eid).limit(1)
        )
        erows: list[dict[str, Any]] = (res_e.data or []) if hasattr(res_e, "data") else []
        emp = erows[0] if erows else {}

        nombre = str(pr.get("nombre_consignatario_final") or "—").strip()
        dni_c = str(pr.get("dni_consignatario") or "").strip() or None
        fer = pr.get("fecha_entrega_real")
        if fer is not None:
            fecha_s = fer.isoformat() if hasattr(fer, "isoformat") else str(fer)[:32]
        else:
            fecha_s = datetime.now(timezone.utc).isoformat()

        return generar_albaran_entrega_pdf(
            datos_empresa=emp,
            datos_porte=pr,
            nombre_consignatario=nombre,
            firma_b64=str(firma),
            fecha_entrega_iso=fecha_s,
            dni_consignatario=dni_c,
        )

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
