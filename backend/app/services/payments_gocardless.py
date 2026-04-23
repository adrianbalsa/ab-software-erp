from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.services.secret_manager_service import get_secret_manager

_log = logging.getLogger(__name__)


class GoCardlessPaymentsError(RuntimeError):
    """Error de integración GoCardless (SDK/API)."""


class GoCardlessPaymentsService:
    def __init__(self) -> None:
        self._client: Any | None = None

    @property
    def _gc(self) -> Any:
        if self._client is not None:
            return self._client
        mgr = get_secret_manager()
        token = mgr.get_gocardless_access_token()
        if not token:
            raise GoCardlessPaymentsError(
                "GoCardless Pro no configurado (falta GOCARDLESS_ACCESS_TOKEN)."
            )
        try:
            import gocardless_pro
        except Exception as exc:  # pragma: no cover - dependiente de entorno
            raise GoCardlessPaymentsError(
                "SDK oficial GoCardless no disponible. Instale `gocardless-pro`."
            ) from exc
        self._client = gocardless_pro.Client(
            access_token=token,
            environment=mgr.get_gocardless_env(),
        )
        return self._client

    async def create_billing_request_flow(
        self,
        *,
        empresa_id: str,
        redirect_uri: str,
    ) -> str:
        eid = str(empresa_id or "").strip()
        ruri = str(redirect_uri or "").strip()
        if not eid:
            raise GoCardlessPaymentsError("empresa_id es obligatorio.")
        if not ruri:
            raise GoCardlessPaymentsError("redirect_uri es obligatoria.")

        idempotency_br = str(uuid.uuid4())
        try:
            billing_request = await asyncio.to_thread(
                lambda: self._gc.billing_requests.create(
                    params={
                        "payment_request_type": "setup_mandate",
                        "mandate_request": {"scheme": "sepa_core"},
                        "metadata": {"empresa_id": eid},
                        "client_reference": eid,
                    },
                    headers={"Idempotency-Key": idempotency_br},
                )
            )
        except Exception as exc:
            _log.warning("gocardless billing_requests.create failed empresa=%s", eid)
            self._capture_sentry(
                "gocardless_billing_request_create_failed",
                exc=exc,
                extra={"empresa_id": eid},
            )
            raise GoCardlessPaymentsError(
                "No se pudo crear la Billing Request de GoCardless."
            ) from exc

        billing_request_id = str(getattr(billing_request, "id", "") or "").strip()
        if not billing_request_id:
            raise GoCardlessPaymentsError("GoCardless no devolvió billing_request id.")

        idempotency_flow = str(uuid.uuid4())
        try:
            flow = await asyncio.to_thread(
                lambda: self._gc.billing_request_flows.create(
                    params={
                        "redirect_uri": ruri,
                        "exit_uri": ruri,
                        "links": {"billing_request": billing_request_id},
                    },
                    headers={"Idempotency-Key": idempotency_flow},
                )
            )
        except Exception as exc:
            _log.warning("gocardless billing_request_flows.create failed empresa=%s", eid)
            self._capture_sentry(
                "gocardless_billing_request_flow_create_failed",
                exc=exc,
                extra={"empresa_id": eid, "billing_request_id": billing_request_id},
            )
            raise GoCardlessPaymentsError(
                "No se pudo crear el Billing Request Flow de GoCardless."
            ) from exc

        # SDK oficial usa `authorisation_url`.
        authorization_url = str(getattr(flow, "authorisation_url", "") or "").strip()
        if not authorization_url:
            raise GoCardlessPaymentsError(
                "GoCardless no devolvió `authorisation_url`."
            )
        return authorization_url

    @staticmethod
    def _capture_sentry(
        message: str,
        *,
        exc: BaseException | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                scope.set_tag("provider", "gocardless")
                scope.set_tag("op", "payments.gocardless")
                if extra:
                    scope.set_context("gocardless", extra)
                if exc is not None:
                    sentry_sdk.capture_exception(exc)
                else:
                    sentry_sdk.capture_message(message, level="error")
        except Exception:
            pass
