from __future__ import annotations

import logging
import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.math_engine import round_fiat, to_decimal
from app.db.supabase import SupabaseAsync
from app.services.audit_logs_service import AuditLogsService

_log = logging.getLogger(__name__)


class PaymentDomainError(ValueError):
    """Error de negocio: datos inválidos, estado no permitido o duplicidad."""


class PaymentIntegrationError(RuntimeError):
    """Fallo de integración externa (SDK/API GoCardless)."""


def _minor_units(amount: Decimal) -> int:
    q = round_fiat(amount)
    if q <= Decimal("0.00"):
        raise PaymentDomainError("El importe de la factura debe ser mayor que 0.")
    cents = q * Decimal("100")
    if cents != cents.to_integral_value():
        raise PaymentDomainError("Importe con más de 2 decimales no permitido.")
    return int(cents)


class PaymentService:
    def __init__(self, db: SupabaseAsync, *, gc_client: Any | None = None) -> None:
        self._db = db
        self._client = gc_client

    @staticmethod
    def _build_client() -> Any:
        cfg = get_settings()
        token = cfg.GOCARDLESS_ACCESS_TOKEN
        if not token:
            raise PaymentIntegrationError(
                "GoCardless Pro no configurado (falta GOCARDLESS_ACCESS_TOKEN)."
            )
        try:
            import gocardless_pro
        except Exception as exc:  # pragma: no cover - dependiente de entorno
            raise PaymentIntegrationError(
                "SDK oficial GoCardless no disponible. Instale `gocardless-pro`."
            ) from exc
        return gocardless_pro.Client(access_token=token, environment=cfg.GOCARDLESS_ENV)

    @property
    def _gc(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def create_customer(
        self,
        *,
        empresa_id: str,
        given_name: str,
        family_name: str,
        email: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        eid = str(empresa_id or "").strip()
        if not eid:
            raise PaymentDomainError("empresa_id es obligatorio.")
        if not given_name.strip() or not family_name.strip():
            raise PaymentDomainError("Nombre y apellido son obligatorios.")

        params: dict[str, Any] = {
            "given_name": given_name.strip(),
            "family_name": family_name.strip(),
            "metadata": {"empresa_id": eid, **(metadata or {})},
        }
        if email and email.strip():
            params["email"] = email.strip()

        try:
            customer = await asyncio.to_thread(
                lambda: self._gc.customers.create(params=params)
            )
        except Exception as exc:
            _log.warning("gocardless create_customer failed empresa=%s", eid)
            raise PaymentIntegrationError("No se pudo crear customer en GoCardless.") from exc

        customer_id = str(getattr(customer, "id", "") or "").strip()
        if not customer_id:
            raise PaymentIntegrationError("Respuesta GoCardless sin customer id.")
        return {
            "customer_id": customer_id,
            "empresa_id": eid,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_one_off_payment_from_invoice(
        self,
        *,
        empresa_id: str,
        factura_id: int,
        customer_id: str,
        mandate_id: str,
        currency: str = "EUR",
    ) -> dict[str, Any]:
        eid = str(empresa_id or "").strip()
        if not eid:
            raise PaymentDomainError("empresa_id es obligatorio.")
        if not str(customer_id or "").strip():
            raise PaymentDomainError("customer_id es obligatorio.")
        if not str(mandate_id or "").strip():
            raise PaymentDomainError("mandate_id es obligatorio.")

        res: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id,empresa_id,total_factura,estado_cobro,pago_id")
            .eq("id", int(factura_id))
            .eq("empresa_id", eid)
            .limit(1)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            raise PaymentDomainError("Factura no encontrada para la empresa.")

        row = rows[0]
        estado = str(row.get("estado_cobro") or "").strip().lower()
        if estado in {"cobrada", "pagada"}:
            raise PaymentDomainError("La factura ya está cobrada.")
        if str(row.get("pago_id") or "").strip():
            raise PaymentDomainError("La factura ya tiene un pago vinculado.")

        total_dec = round_fiat(to_decimal(row.get("total_factura") or 0))
        amount_minor = _minor_units(total_dec)
        currency_code = str(currency or "EUR").strip().upper() or "EUR"
        idem = str(uuid.uuid4())

        payload = {
            "amount": amount_minor,
            "currency": currency_code,
            "links": {"mandate": str(mandate_id).strip()},
            "metadata": {
                "factura_id": str(int(factura_id)),
                "empresa_id": eid,
                "customer_id": str(customer_id).strip(),
            },
        }

        try:
            payment = await asyncio.to_thread(
                lambda: self._gc.payments.create(
                    params=payload,
                    headers={"Idempotency-Key": idem},
                )
            )
        except Exception as exc:
            _log.warning("gocardless create_payment failed empresa=%s factura=%s", eid, int(factura_id))
            raise PaymentIntegrationError("No se pudo crear el pago en GoCardless.") from exc

        payment_id = str(getattr(payment, "id", "") or "").strip()
        payment_status = str(getattr(payment, "status", "") or "created").strip()
        if not payment_id:
            raise PaymentIntegrationError("Respuesta GoCardless sin payment id.")

        now_iso = datetime.now(timezone.utc).isoformat()
        pago_ref = f"gocardless:{payment_id}"
        await self._db.execute(
            self._db.table("facturas")
            .update({"pago_id": pago_ref})
            .eq("id", int(factura_id))
            .eq("empresa_id", eid)
        )

        await AuditLogsService(self._db).log_sensitive_action(
            empresa_id=eid,
            table_name="facturas",
            record_id=str(int(factura_id)),
            action="UPDATE",
            old_value={"pago_id": row.get("pago_id"), "estado_cobro": row.get("estado_cobro")},
            new_value={
                "factura_id": int(factura_id),
                "empresa_id": eid,
                "customer_id": str(customer_id).strip(),
                "payment_id": payment_id,
                "status": payment_status,
                "timestamp": now_iso,
                "amount": str(total_dec),
                "currency": currency_code,
            },
            user_id=None,
        )

        return {
            "factura_id": int(factura_id),
            "empresa_id": eid,
            "customer_id": str(customer_id).strip(),
            "payment_id": payment_id,
            "status": payment_status,
            "amount": str(total_dec),
            "currency": currency_code,
            "timestamp": now_iso,
        }

    async def create_mandate_setup_flow(self, cliente_id: str, success_url: str) -> dict[str, str]:
        cid = str(cliente_id or "").strip()
        if not cid:
            raise PaymentDomainError("cliente_id es obligatorio.")
        surl = str(success_url or "").strip()
        if not surl:
            raise PaymentDomainError("success_url es obligatoria.")

        res_cli: Any = await self._db.execute(
            self._db.table("clientes")
            .select("id,empresa_id,nombre,email")
            .eq("id", cid)
            .limit(1)
        )
        cli_rows: list[dict[str, Any]] = (res_cli.data or []) if hasattr(res_cli, "data") else []
        if not cli_rows:
            raise PaymentDomainError("Cliente no encontrado.")
        cliente = cli_rows[0]
        empresa_id = str(cliente.get("empresa_id") or "").strip()
        if not empresa_id:
            raise PaymentDomainError("Cliente sin empresa asociada.")

        gocardless_customer_id = ""
        try:
            res_prof: Any = await self._db.execute(
                self._db.table("profiles")
                .select("id,gocardless_customer_id")
                .eq("cliente_id", cid)
                .limit(1)
            )
            prof_rows: list[dict[str, Any]] = (res_prof.data or []) if hasattr(res_prof, "data") else []
            if prof_rows:
                gocardless_customer_id = str(prof_rows[0].get("gocardless_customer_id") or "").strip()
        except Exception:
            # Compat con esquemas donde aún no existe profiles.gocardless_customer_id
            gocardless_customer_id = ""

        if not gocardless_customer_id:
            raw_name = str(cliente.get("nombre") or "").strip()
            given_name = raw_name.split(" ", 1)[0] if raw_name else "Cliente"
            family_name = raw_name.split(" ", 1)[1] if " " in raw_name else "AB Logistics"
            created = await self.create_customer(
                empresa_id=empresa_id,
                given_name=given_name,
                family_name=family_name,
                email=(str(cliente.get("email") or "").strip() or None),
                metadata={"cliente_id": cid},
            )
            gocardless_customer_id = str(created.get("customer_id") or "").strip()
            if not gocardless_customer_id:
                raise PaymentIntegrationError("No se pudo obtener customer_id de GoCardless.")
            try:
                await self._db.execute(
                    self._db.table("profiles")
                    .update({"gocardless_customer_id": gocardless_customer_id})
                    .eq("cliente_id", cid)
                )
            except Exception:
                # Si la columna no existe aún, seguimos; no bloquea el flujo.
                _log.info("profiles.gocardless_customer_id no disponible para persistencia")

        idem_br = str(uuid.uuid4())
        try:
            billing_request = await asyncio.to_thread(
                lambda: self._gc.billing_requests.create(
                    params={
                        "mandate_request": {
                            "currency": "EUR",
                            "scheme": "sepa_core",
                        },
                        "links": {"customer": gocardless_customer_id},
                    },
                    headers={"Idempotency-Key": idem_br},
                )
            )
        except Exception as exc:
            raise PaymentIntegrationError(
                "No se pudo crear el billing_request para mandato."
            ) from exc

        billing_request_id = str(getattr(billing_request, "id", "") or "").strip()
        if not billing_request_id:
            raise PaymentIntegrationError("Respuesta GoCardless sin billing_request id.")

        idem_flow = str(uuid.uuid4())
        try:
            br_flow = await asyncio.to_thread(
                lambda: self._gc.billing_request_flows.create(
                    params={
                        "redirect_uri": surl,
                        "exit_uri": surl,
                        "links": {"billing_request": billing_request_id},
                    },
                    headers={"Idempotency-Key": idem_flow},
                )
            )
        except Exception as exc:
            raise PaymentIntegrationError(
                "No se pudo crear el flujo de autorización de mandato."
            ) from exc

        redirect_url = str(getattr(br_flow, "authorisation_url", "") or "").strip()
        if not redirect_url:
            raise PaymentIntegrationError("Respuesta GoCardless sin authorisation_url.")

        now_iso = datetime.now(timezone.utc).isoformat()
        await AuditLogsService(self._db).log_sensitive_action(
            empresa_id=empresa_id,
            table_name="clientes",
            record_id=cid,
            action="UPDATE",
            old_value=None,
            new_value={
                "evento": "mandate_setup_initiated",
                "cliente_id": cid,
                "empresa_id": empresa_id,
                "gocardless_customer_id": gocardless_customer_id,
                "billing_request_id": billing_request_id,
                "timestamp": now_iso,
            },
            user_id=None,
        )

        return {"redirect_url": redirect_url}

