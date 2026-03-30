from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.encryption import decrypt_str, encrypt_str
from app.db.supabase import SupabaseAsync
from app.services.reconciliation_service import ReconciliationService, match_invoice_transaction_pair

_log = logging.getLogger(__name__)

# GoCardless Bank Account Data API v2 (ex-Nordigen)
_GOCARDLESS_API_V2 = "https://bankaccountdata.gocardless.com/api/v2"


@dataclass(frozen=True, slots=True)
class BankSyncResult:
    """Resultado de una sincronización + conciliación."""

    transacciones_procesadas: int
    coincidencias: int
    detalle: list[dict[str, Any]]


def _gocardless_configured() -> bool:
    s = get_settings()
    return bool(s.GOCARDLESS_SECRET_ID and s.GOCARDLESS_SECRET_KEY)


async def _fetch_access_token() -> str:
    s = get_settings()
    if not s.GOCARDLESS_SECRET_ID or not s.GOCARDLESS_SECRET_KEY:
        raise RuntimeError("GOCARDLESS_SECRET_ID y GOCARDLESS_SECRET_KEY son obligatorios")
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(
            f"{_GOCARDLESS_API_V2}/token/new/",
            json={
                "secret_id": s.GOCARDLESS_SECRET_ID,
                "secret_key": s.GOCARDLESS_SECRET_KEY,
            },
        )
        if r.status_code != 200:
            raise RuntimeError(f"GoCardless token HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        return str(data["access"])


def _parse_tx_date(tx: dict[str, Any]) -> date | None:
    raw = tx.get("bookingDate") or tx.get("valueDate") or tx.get("booking_date")
    if not raw:
        return None
    s = str(raw).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _tx_amount_eur(tx: dict[str, Any]) -> float:
    ta = tx.get("transactionAmount") or {}
    try:
        return float(str(ta.get("amount", "0")).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _tx_id(tx: dict[str, Any]) -> str:
    return str(
        tx.get("transactionId")
        or tx.get("internalTransactionId")
        or tx.get("entryReference")
        or ""
    )


def _stable_tx_id(tx: dict[str, Any]) -> str:
    tid = _tx_id(tx).strip()
    if tid:
        return tid
    raw = f"{tx.get('bookingDate')}|{tx.get('valueDate')}|{_tx_amount_eur(tx)}|{tx.get('entryReference')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def _tx_description(tx: dict[str, Any]) -> str:
    parts: list[str] = []
    ri = tx.get("remittanceInformationUnstructured")
    if ri:
        parts.append(str(ri))
    ria = tx.get("remittanceInformationUnstructuredArray")
    if isinstance(ria, list):
        for x in ria:
            if x:
                parts.append(str(x))
    if not parts:
        for key in ("additionalInformation", "creditorName", "debtorName"):
            v = tx.get(key)
            if v:
                parts.append(str(v))
    return " ".join(parts)[:4000]


def _flatten_transactions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza respuesta de /accounts/{id}/transactions/."""
    out: list[dict[str, Any]] = []
    root = payload.get("transactions")
    if isinstance(root, list):
        return [x for x in root if isinstance(x, dict)]
    if isinstance(root, dict):
        for key in ("booked", "pending"):
            for b in root.get(key) or []:
                if isinstance(b, dict):
                    out.append(b)
        return out
    if isinstance(payload, dict):
        for key in ("booked", "pending"):
            for b in payload.get(key) or []:
                if isinstance(b, dict):
                    out.append(b)
    return out


class BankService:
    """GoCardless Bank Account Data + persistencia en ``bank_transactions`` + conciliación."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def exchange_token(self) -> str:
        """Intercambia credenciales de servidor por JWT de acceso a la API (no registrar secretos en logs)."""
        return await _fetch_access_token()

    async def _load_requisition_id(self, empresa_id: str) -> str:
        for table in ("empresa_bank_accounts", "empresa_banco_sync"):
            res: Any = await self._db.execute(
                self._db.table(table).select("requisition_id_enc").eq("empresa_id", empresa_id).limit(1)
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if rows:
                return decrypt_str(str(rows[0]["requisition_id_enc"]))
        raise ValueError("No hay banco conectado para esta empresa")

    async def create_requisition_link(
        self,
        *,
        empresa_id: str,
        institution_id: str,
        redirect_url: str | None = None,
    ) -> dict[str, str]:
        """Alias de ``get_auth_link`` (enlace de autorización bancaria)."""
        return await self.get_auth_link(
            empresa_id=empresa_id,
            institution_id=institution_id,
            redirect_url=redirect_url,
        )

    async def get_auth_link(
        self,
        *,
        empresa_id: str,
        institution_id: str,
        redirect_url: str | None = None,
    ) -> dict[str, str]:
        """
        Crea requisición en GoCardless y persiste ``requisition_id`` cifrado
        (``empresa_bank_accounts`` y ``empresa_banco_sync``).
        """
        if not _gocardless_configured():
            raise RuntimeError("Integración GoCardless no configurada en el servidor")

        access = await _fetch_access_token()
        redir = (redirect_url or "").strip()
        if not redir:
            pub = get_settings().PUBLIC_APP_URL or "http://localhost:3000"
            redir = pub.rstrip("/") + "/bancos/callback"

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{_GOCARDLESS_API_V2}/requisitions/",
                headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
                json={
                    "redirect": redir,
                    "institution_id": institution_id.strip(),
                    "reference": str(empresa_id),
                    "user_language": "ES",
                },
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"GoCardless requisitions HTTP {r.status_code}: {r.text[:800]}")
            data = r.json()

        req_id = str(data.get("id") or "").strip()
        link = str(data.get("link") or "").strip()
        if not req_id or not link:
            raise RuntimeError("Respuesta GoCardless sin id o link de requisición")

        now = datetime.now(timezone.utc).isoformat()
        inst = institution_id.strip()

        payload_new: dict[str, Any] = {
            "empresa_id": empresa_id,
            "requisition_id_enc": encrypt_str(req_id),
            "institution_id": inst,
            "updated_at": now,
        }
        res_chk: Any = await self._db.execute(
            self._db.table("empresa_bank_accounts").select("id").eq("empresa_id", empresa_id).limit(1)
        )
        exist_new: list[dict[str, Any]] = (res_chk.data or []) if hasattr(res_chk, "data") else []
        if exist_new:
            await self._db.execute(
                self._db.table("empresa_bank_accounts").update(payload_new).eq("empresa_id", empresa_id)
            )
        else:
            await self._db.execute(self._db.table("empresa_bank_accounts").insert(payload_new))

        payload_legacy: dict[str, Any] = {
            "empresa_id": empresa_id,
            "requisition_id_enc": encrypt_str(req_id),
            "access_token_enc": encrypt_str(access),
            "institution_id": inst,
            "updated_at": now,
        }
        res_legacy: Any = await self._db.execute(
            self._db.table("empresa_banco_sync").select("id").eq("empresa_id", empresa_id).limit(1)
        )
        exist_leg: list[dict[str, Any]] = (res_legacy.data or []) if hasattr(res_legacy, "data") else []
        if exist_leg:
            await self._db.execute(
                self._db.table("empresa_banco_sync").update(payload_legacy).eq("empresa_id", empresa_id)
            )
        else:
            await self._db.execute(self._db.table("empresa_banco_sync").insert(payload_legacy))

        return {"link": link, "requisition_id": req_id}

    async def get_transactions(
        self,
        *,
        requisition_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Descarga movimientos (todas las cuentas vinculadas a la requisición).
        """
        if not _gocardless_configured():
            raise RuntimeError("Integración GoCardless no configurada en el servidor")

        access = await _fetch_access_token()

        async with httpx.AsyncClient(timeout=60.0) as client:
            rr = await client.get(
                f"{_GOCARDLESS_API_V2}/requisitions/{requisition_id}/",
                headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
            )
            if rr.status_code != 200:
                raise RuntimeError(f"GoCardless requisition HTTP {rr.status_code}: {rr.text[:500]}")
            req = rr.json()

        accounts = req.get("accounts") or []
        if isinstance(accounts, str):
            accounts = [accounts]

        all_tx: list[dict[str, Any]] = []
        df = date_from.isoformat() if date_from else None
        dt = date_to.isoformat() if date_to else None

        async with httpx.AsyncClient(timeout=60.0) as client:
            for acc in accounts:
                aid = str(acc).strip()
                if not aid:
                    continue
                params: dict[str, str] = {}
                if df:
                    params["date_from"] = df
                if dt:
                    params["date_to"] = dt
                tr = await client.get(
                    f"{_GOCARDLESS_API_V2}/accounts/{aid}/transactions/",
                    headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
                    params=params,
                )
                if tr.status_code != 200:
                    _log.warning("GoCardless transactions cuenta HTTP %s", tr.status_code)
                    continue
                payload = tr.json()
                all_tx.extend(_flatten_transactions(payload))

        return all_tx

    async def _save_primary_account_id(self, empresa_id: str, requisition_id: str) -> None:
        access = await _fetch_access_token()
        async with httpx.AsyncClient(timeout=60.0) as client:
            rr = await client.get(
                f"{_GOCARDLESS_API_V2}/requisitions/{requisition_id}/",
                headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
            )
            if rr.status_code != 200:
                return
            req = rr.json()
        accounts = req.get("accounts") or []
        if isinstance(accounts, str):
            accounts = [accounts]
        if not accounts:
            return
        aid = str(accounts[0]).strip()
        if not aid:
            return
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            self._db.table("empresa_bank_accounts")
            .update({"account_id_enc": encrypt_str(aid), "updated_at": now})
            .eq("empresa_id", empresa_id)
        )

    async def get_bank_transactions(self, account_id: str) -> list[dict[str, Any]]:
        """
        Scaffold SEPA/Open Banking:
        devuelve los movimientos persistidos para una cuenta de empresa.
        """
        account_id_clean = str(account_id or "").strip()
        if not account_id_clean:
            return []
        res: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("account_id", account_id_clean)
            .order("booked_date", desc=True)
        )
        return (res.data or []) if hasattr(res, "data") else []

    @staticmethod
    def _quantize_half_even(value: Any) -> Decimal:
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        except Exception:
            return Decimal("0.00")

    async def match_invoice_to_transaction(self, invoice_id: int, tx_id: str) -> dict[str, Any]:
        """
        Match manual invoice<->transaction con reglas de conciliaci?n (importe + referencia/concepto).
        [cite: 2026-03-30]
        """
        inv_id = int(invoice_id)
        tx_id_clean = str(tx_id or "").strip()
        if not tx_id_clean:
            raise ValueError("tx_id es obligatorio")

        res_inv: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id, empresa_id, total_factura, numero_factura, num_factura")
            .eq("id", inv_id)
            .limit(1)
        )
        inv_rows: list[dict[str, Any]] = (res_inv.data or []) if hasattr(res_inv, "data") else []
        if not inv_rows:
            raise ValueError("Factura no encontrada")
        invoice = dict(inv_rows[0])

        res_tx: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("empresa_id, transaction_id, amount, description, reference, concept, concepto, booked_date")
            .eq("transaction_id", tx_id_clean)
            .limit(1)
        )
        tx_rows: list[dict[str, Any]] = (res_tx.data or []) if hasattr(res_tx, "data") else []
        if not tx_rows:
            raise ValueError("Transacci?n no encontrada")
        tx = dict(tx_rows[0])

        if str(invoice.get("empresa_id") or "") != str(tx.get("empresa_id") or ""):
            raise ValueError("Factura y transacci?n no pertenecen a la misma empresa")

        if not match_invoice_transaction_pair(invoice=invoice, transaction=tx):
            raise ValueError("No cumple reglas de conciliaci?n por importe y referencia/concepto")

        fecha = tx.get("booked_date")
        fecha_cobro_real = (
            fecha.isoformat()[:10] if hasattr(fecha, "isoformat") else str(fecha or "")[:10]
        ) or date.today().isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            self._db.table("facturas")
            .update(
                {
                    "estado_cobro": "cobrada",
                    "payment_status": "PAID",
                    "pago_id": tx_id_clean,
                    "matched_transaction_id": tx_id_clean,
                    "fecha_cobro_real": fecha_cobro_real,
                }
            )
            .eq("id", inv_id)
            .eq("empresa_id", str(invoice.get("empresa_id") or ""))
        )
        await self._db.execute(
            self._db.table("bank_transactions")
            .update({"reconciled": True, "updated_at": now_iso})
            .eq("empresa_id", str(tx.get("empresa_id") or ""))
            .eq("transaction_id", tx_id_clean)
        )

        return {
            "invoice_id": inv_id,
            "transaction_id": tx_id_clean,
            "payment_status": "PAID",
            "importe_factura": float(self._quantize_half_even(invoice.get("total_factura"))),
            "importe_transaccion": float(self._quantize_half_even(tx.get("amount"))),
            "matched": True,
        }

    def _api_tx_to_db_row(self, empresa_id: str, tx: dict[str, Any]) -> dict[str, Any] | None:
        tid = _stable_tx_id(tx)
        if not tid:
            return None
        amt = _tx_amount_eur(tx)
        bd = _parse_tx_date(tx)
        if bd is None:
            return None
        ta = tx.get("transactionAmount") or {}
        cur = str(ta.get("currency") or "EUR")[:8]
        desc = _tx_description(tx)
        fp = hashlib.sha256(tid.encode("utf-8")).hexdigest()
        return {
            "empresa_id": empresa_id,
            "transaction_id": tid[:512],
            "amount": round(amt, 2),
            "booked_date": bd.isoformat(),
            "currency": cur,
            "description": desc,
            "reconciled": False,
            "raw_fingerprint": fp,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def fetch_recent_transactions(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        """
        Descarga movimientos de GoCardless y los upserta en ``bank_transactions``.
        No registra el contenido crudo de los movimientos (PII / GDPR).
        """
        req_plain = await self._load_requisition_id(empresa_id)
        await self._save_primary_account_id(empresa_id, req_plain)

        if date_to is None:
            date_to = date.today()
        if date_from is None:
            date_from = date_to - timedelta(days=90)

        movs = await self.get_transactions(
            requisition_id=req_plain,
            date_from=date_from,
            date_to=date_to,
        )

        rows: list[dict[str, Any]] = []
        for tx in movs:
            row = self._api_tx_to_db_row(empresa_id, tx)
            if row:
                rows.append(row)

        if not rows:
            return 0

        await self._db.execute(
            self._db.table("bank_transactions").upsert(rows, on_conflict="empresa_id,transaction_id")
        )
        return len(rows)

    async def sincronizar_y_conciliar(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> BankSyncResult:
        """
        Persiste movimientos y ejecuta conciliación automática (importe + número en concepto).
        """
        if not _gocardless_configured():
            raise RuntimeError("Integración GoCardless no configurada en el servidor")

        n_written = await self.fetch_recent_transactions(
            empresa_id=empresa_id,
            date_from=date_from,
            date_to=date_to,
        )

        fresh = await _fetch_access_token()
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            self._db.table("empresa_banco_sync")
            .update({"access_token_enc": encrypt_str(fresh), "updated_at": now})
            .eq("empresa_id", empresa_id)
        )

        recon = ReconciliationService(self._db)
        coincidencias, detalle = await recon.auto_reconcile_invoices(empresa_id)

        return BankSyncResult(
            transacciones_procesadas=max(n_written, 0),
            coincidencias=coincidencias,
            detalle=detalle,
        )
