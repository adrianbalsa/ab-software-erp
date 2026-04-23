from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.secret_manager_service import get_secret_manager
from app.core.security import fernet_decrypt_string, fernet_encrypt_string
from app.db.supabase import SupabaseAsync
from app.services.audit_logs_service import AuditLogsService
from app.services.reconciliation_service import ReconciliationService, match_invoice_transaction_pair
from app.services.math_engine import BankingMathEngineService

_log = logging.getLogger(__name__)

# GoCardless Bank Account Data API v2 (ex-Nordigen)
_GOCARDLESS_API_V2 = "https://bankaccountdata.gocardless.com/api/v2"


@dataclass(frozen=True, slots=True)
class BankSyncResult:
    """Resultado de una sincronizaci?n + conciliaci?n."""

    transacciones_procesadas: int
    coincidencias: int
    detalle: list[dict[str, Any]]


def _gocardless_configured() -> bool:
    m = get_secret_manager()
    return bool(m.get_gocardless_secret_id() and m.get_gocardless_secret_key())


def _encrypt_bank_token(plain: str | None) -> str | None:
    """Cifra tokens/IDs bancarios antes de persistir (Fernet v?a ``security``)."""
    return fernet_encrypt_string((plain or "").strip() or None)


def _decrypt_bank_token(cipher: str | None) -> str:
    """Descifra valor persistido; cadena vac?a si no hay dato."""
    if not cipher or not str(cipher).strip():
        return ""
    out = fernet_decrypt_string(str(cipher).strip())
    return (out or "").strip()


async def _fetch_access_token() -> str:
    m = get_secret_manager()
    sid = m.get_gocardless_secret_id()
    skey = m.get_gocardless_secret_key()
    if not sid or not skey:
        raise RuntimeError("GOCARDLESS_SECRET_ID y GOCARDLESS_SECRET_KEY son obligatorios")
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(
            f"{_GOCARDLESS_API_V2}/token/new/",
            json={
                "secret_id": sid,
                "secret_key": skey,
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


def _tx_currency(tx: dict[str, Any]) -> str:
    ta = tx.get("transactionAmount") or {}
    return str(ta.get("currency") or "EUR")[:8]


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


def _remittance_info(tx: dict[str, Any]) -> str:
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


def _tx_description(tx: dict[str, Any]) -> str:
    return _remittance_info(tx)


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


def _mask_iban_tail(iban: str | None) -> str | None:
    if not iban:
        return None
    s = re.sub(r"\s+", "", str(iban).upper())
    if len(s) < 8:
        return "****"
    return f"****{s[-4:]}"


class BankService:
    """GoCardless Bank Account Data (Nordigen) + ``bank_accounts`` / ``bank_transactions``."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def exchange_token(self) -> str:
        """JWT de acceso de corta duraci?n para llamadas a la API (no persistir en logs)."""
        return await _fetch_access_token()

    async def get_institutions(self, *, country_code: str = "ES") -> list[dict[str, Any]]:
        """Lista instituciones disponibles para un país (PSD2)."""
        if not _gocardless_configured():
            raise RuntimeError("Integración GoCardless no configurada en el servidor")
        country = (country_code or "ES").strip().upper()[:2] or "ES"
        access = await _fetch_access_token()
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.get(
                f"{_GOCARDLESS_API_V2}/institutions/",
                headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
                params={"country": country},
            )
            if r.status_code != 200:
                raise RuntimeError(f"GoCardless institutions HTTP {r.status_code}: {r.text[:500]}")
            data = r.json()
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            rows = data.get("results")
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
        return []

    async def _load_requisition_id(self, empresa_id: str) -> str:
        for table in ("empresa_bank_accounts", "empresa_banco_sync"):
            res: Any = await self._db.execute(
                self._db.table(table).select("requisition_id_enc").eq("empresa_id", empresa_id).limit(1)
            )
            rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
            if rows:
                rid = _decrypt_bank_token(str(rows[0].get("requisition_id_enc") or ""))
                if rid:
                    return rid
        raise ValueError("No hay banco conectado para esta empresa")

    async def get_requisition_link(
        self,
        *,
        empresa_id: str,
        institution_id: str,
        redirect_url: str | None = None,
    ) -> dict[str, str]:
        """Enlace de autorizaci?n del usuario hacia su banco (crea requisici?n GoCardless)."""
        return await self.get_auth_link(
            empresa_id=empresa_id,
            institution_id=institution_id,
            redirect_url=redirect_url,
        )

    async def create_requisition_link(
        self,
        *,
        empresa_id: str,
        institution_id: str,
        redirect_url: str | None = None,
    ) -> dict[str, str]:
        """Alias retrocompatible de ``get_requisition_link``."""
        return await self.get_requisition_link(
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
        Crea requisici?n en GoCardless y persiste ``requisition_id`` cifrado
        (``empresa_bank_accounts`` y ``empresa_banco_sync``).
        """
        if not _gocardless_configured():
            raise RuntimeError("Integraci?n GoCardless no configurada en el servidor")

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
            raise RuntimeError("Respuesta GoCardless sin id o link de requisici?n")

        now = datetime.now(timezone.utc).isoformat()
        inst = institution_id.strip()
        req_enc = _encrypt_bank_token(req_id)
        if not req_enc:
            raise RuntimeError("No se pudo cifrar requisition_id")

        payload_new: dict[str, Any] = {
            "empresa_id": empresa_id,
            "requisition_id_enc": req_enc,
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

        tok_enc = _encrypt_bank_token(access)
        payload_legacy: dict[str, Any] = {
            "empresa_id": empresa_id,
            "requisition_id_enc": req_enc,
            "access_token_enc": tok_enc,
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

    async def _get_requisition_json(self, client: httpx.AsyncClient, access: str, requisition_id: str) -> dict[str, Any]:
        rr = await client.get(
            f"{_GOCARDLESS_API_V2}/requisitions/{requisition_id}/",
            headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
        )
        if rr.status_code != 200:
            raise RuntimeError(f"GoCardless requisition HTTP {rr.status_code}: {rr.text[:500]}")
        data = rr.json()
        if not isinstance(data, dict):
            raise RuntimeError("Respuesta de requisici?n inv?lida")
        return data

    async def list_accounts(self, *, empresa_id: str) -> list[dict[str, Any]]:
        """
        Cuentas bancarias enlazadas tras la autorizaci?n (detalle por ``/accounts/{id}/``).
        Persiste filas en ``public.bank_accounts`` si faltan.
        """
        if not _gocardless_configured():
            raise RuntimeError("Integraci?n GoCardless no configurada en el servidor")
        req_plain = await self._load_requisition_id(empresa_id)
        access = await _fetch_access_token()
        tok_row_enc = _encrypt_bank_token(access)
        async with httpx.AsyncClient(timeout=60.0) as client:
            req = await self._get_requisition_json(client, access, req_plain)
            accounts = req.get("accounts") or []
            if isinstance(accounts, str):
                accounts = [accounts]
            inst = str(req.get("institution_id") or "").strip()
            out: list[dict[str, Any]] = []
            now = datetime.now(timezone.utc).isoformat()
            for acc in accounts:
                aid = str(acc).strip()
                if not aid:
                    continue
                ar = await client.get(
                    f"{_GOCARDLESS_API_V2}/accounts/{aid}/",
                    headers={"Authorization": f"Bearer {access}", "accept": "application/json"},
                )
                if ar.status_code != 200:
                    _log.warning("GoCardless account %s HTTP %s", aid, ar.status_code)
                    continue
                raw_body = ar.json()
                acc_json = raw_body if isinstance(raw_body, dict) else {}
                meta = acc_json.get("account") if isinstance(acc_json.get("account"), dict) else acc_json
                if not isinstance(meta, dict):
                    meta = {}
                iban = meta.get("iban")
                cur = str(meta.get("currency") or "EUR")[:8]
                masked = _mask_iban_tail(str(iban) if iban else None)
                row_ins = {
                    "empresa_id": empresa_id,
                    "gocardless_account_id": aid,
                    "institution_id": inst or None,
                    "iban_masked": masked,
                    "currency": cur,
                    "status": "linked",
                    "updated_at": now,
                }
                if tok_row_enc:
                    row_ins["access_token_encrypted"] = tok_row_enc
                res_e: Any = await self._db.execute(
                    self._db.table("bank_accounts")
                    .select("id")
                    .eq("empresa_id", empresa_id)
                    .eq("gocardless_account_id", aid)
                    .limit(1)
                )
                ex = (res_e.data or []) if hasattr(res_e, "data") else []
                if ex:
                    await self._db.execute(
                        self._db.table("bank_accounts").update(row_ins).eq("id", str(ex[0]["id"]))
                    )
                    row_id = str(ex[0]["id"])
                else:
                    row_ins["created_at"] = now
                    await self._db.execute(self._db.table("bank_accounts").insert(row_ins))
                    res_ins: Any = await self._db.execute(
                        self._db.table("bank_accounts")
                        .select("id")
                        .eq("empresa_id", empresa_id)
                        .eq("gocardless_account_id", aid)
                        .limit(1)
                    )
                    ins_rows = (res_ins.data or []) if hasattr(res_ins, "data") else []
                    row_id = str(ins_rows[0]["id"]) if ins_rows else ""

                out.append(
                    {
                        "id": row_id,
                        "gocardless_account_id": aid,
                        "institution_id": inst or None,
                        "iban_masked": masked,
                        "currency": cur,
                    }
                )

            if accounts:
                await self._db.execute(
                    self._db.table("empresa_bank_accounts")
                    .update(
                        {
                            "account_id_enc": _encrypt_bank_token(str(accounts[0]).strip()),
                            "updated_at": now,
                        }
                    )
                    .eq("empresa_id", empresa_id)
                )
        return out

    async def get_transactions(
        self,
        *,
        requisition_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """Descarga movimientos en bruto (todas las cuentas de la requisici?n)."""
        if not _gocardless_configured():
            raise RuntimeError("Integraci?n GoCardless no configurada en el servidor")

        access = await _fetch_access_token()

        async with httpx.AsyncClient(timeout=60.0) as client:
            req = await self._get_requisition_json(client, access, requisition_id)

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
                for part in _flatten_transactions(payload):
                    if isinstance(part, dict):
                        all_tx.append({**part, "_gocardless_account_id": aid})

        return all_tx

    async def fetch_transactions(
        self,
        *,
        empresa_id: str,
        days: int = 90,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        ?ltimos ``days`` d?as (por defecto 90): persiste en ``bank_transactions`` y devuelve filas normalizadas.
        """
        n, rows = await self._fetch_and_store_transactions(
            empresa_id=empresa_id,
            date_from=date_from,
            date_to=date_to,
            days=days,
        )
        _ = n
        return rows

    async def complete_oauth_redirect(
        self,
        *,
        empresa_id: str,
        ref: str,
        days: int = 90,
    ) -> dict[str, Any]:
        """
        Tras el redirect de GoCardless, ``ref`` es el ``requisition_id``.
        Verifica coherencia con lo persistido, sincroniza cuentas y devuelve movimientos recientes.
        """
        ref = str(ref or "").strip()
        if not ref:
            raise ValueError("Par?metro ref (requisition_id) obligatorio")
        stored = await self._load_requisition_id(empresa_id)
        if stored != ref:
            raise ValueError("La requisici?n no coincide con el v?nculo bancario de esta empresa")
        accounts = await self.list_accounts(empresa_id=empresa_id)
        n, txs = await self._fetch_and_store_transactions(empresa_id=empresa_id, days=days)
        return {
            "requisition_id": ref,
            "accounts": accounts,
            "transactions_imported": n,
            "transactions": txs,
        }

    def _api_tx_to_db_row(
        self,
        empresa_id: str,
        tx: dict[str, Any],
        *,
        bank_account_uuid: str | None,
        gocardless_account_id: str | None,
    ) -> dict[str, Any] | None:
        tid = _stable_tx_id(tx)
        if not tid:
            return None
        amt = _tx_amount_eur(tx)
        bd = _parse_tx_date(tx)
        if bd is None:
            return None
        cur = _tx_currency(tx)
        desc = _tx_description(tx)
        rem = _remittance_info(tx)
        fp = hashlib.sha256(tid.encode("utf-8")).hexdigest()
        row: dict[str, Any] = {
            "empresa_id": empresa_id,
            "transaction_id": tid[:512],
            "amount": round(amt, 2),
            "booked_date": bd.isoformat(),
            "currency": cur,
            "description": desc,
            "remittance_info": rem,
            "internal_status": "imported",
            "reconciled": False,
            "status_reconciled": "pending",
            "raw_fingerprint": fp,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if gocardless_account_id:
            row["gocardless_account_id"] = gocardless_account_id
        if bank_account_uuid:
            row["bank_account_id"] = bank_account_uuid
        return row

    async def _resolve_bank_account_row_id(
        self, *, empresa_id: str, gocardless_account_id: str
    ) -> str | None:
        res: Any = await self._db.execute(
            self._db.table("bank_accounts")
            .select("id")
            .eq("empresa_id", empresa_id)
            .eq("gocardless_account_id", gocardless_account_id)
            .limit(1)
        )
        rows = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return None
        return str(rows[0].get("id") or "") or None

    async def _fetch_and_store_transactions(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
        days: int = 90,
    ) -> tuple[int, list[dict[str, Any]]]:
        req_plain = await self._load_requisition_id(empresa_id)
        await self.list_accounts(empresa_id=empresa_id)

        if date_to is None:
            date_to = date.today()
        if date_from is None:
            date_from = date_to - timedelta(days=max(1, min(days, 365)))

        try:
            import sentry_sdk
        except Exception:  # pragma: no cover
            sentry_sdk = None  # type: ignore[assignment]

        if sentry_sdk is not None:
            with sentry_sdk.start_span(op="banking.sync", name="fetch_bank_transactions"):
                movs = await self.get_transactions(
                    requisition_id=req_plain,
                    date_from=date_from,
                    date_to=date_to,
                )
        else:
            movs = await self.get_transactions(
                requisition_id=req_plain,
                date_from=date_from,
                date_to=date_to,
            )

        rows: list[dict[str, Any]] = []
        normalized: list[dict[str, Any]] = []
        for tx in movs:
            if not isinstance(tx, dict):
                continue
            gc_aid = str(tx.get("_gocardless_account_id") or "").strip() or None
            tx_db = {k: v for k, v in tx.items() if k != "_gocardless_account_id"}
            bac_uuid = None
            if gc_aid:
                bac_uuid = await self._resolve_bank_account_row_id(
                    empresa_id=empresa_id, gocardless_account_id=gc_aid
                )
            row = self._api_tx_to_db_row(
                empresa_id,
                tx_db,
                bank_account_uuid=bac_uuid,
                gocardless_account_id=gc_aid,
            )
            if row:
                rows.append(row)
                normalized.append(
                    {
                        "transaction_id": row["transaction_id"],
                        "booking_date": row["booked_date"],
                        "amount": row["amount"],
                        "currency": row["currency"],
                        "remittance_info": row.get("remittance_info"),
                        "internal_status": row.get("internal_status"),
                        "description": row.get("description"),
                    }
                )

        if not rows:
            return 0, []

        await self._db.execute(
            self._db.table("bank_transactions").upsert(rows, on_conflict="empresa_id,transaction_id")
        )
        return len(rows), normalized

    async def fetch_recent_transactions(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        """Descarga movimientos (90 d?as por defecto) y upsert en ``bank_transactions``; devuelve conteo."""
        n, _ = await self._fetch_and_store_transactions(
            empresa_id=empresa_id, date_from=date_from, date_to=date_to, days=90
        )
        return n

    async def get_bank_transactions(self, gocardless_account_id: str) -> list[dict[str, Any]]:
        """Movimientos persistidos para una cuenta GoCardless (UUID de la API)."""
        aid = str(gocardless_account_id or "").strip()
        if not aid:
            return []
        res: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("gocardless_account_id", aid)
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
            .select("*")
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
            .update(
                {
                    "reconciled": True,
                    "internal_status": "reconciled",
                    "status_reconciled": "reconciled",
                    "updated_at": now_iso,
                }
            )
            .eq("empresa_id", str(tx.get("empresa_id") or ""))
            .eq("transaction_id", tx_id_clean)
        )
        try:
            await AuditLogsService(self._db).log_bank_reconciliation(
                empresa_id=str(invoice.get("empresa_id") or ""),
                transaction_id=tx_id_clean,
                factura_id=inv_id,
                user_id=None,
            )
        except Exception:
            _log.warning(
                "match_invoice_to_transaction: audit log omitido tx=%s",
                tx_id_clean,
                exc_info=True,
            )

        return {
            "invoice_id": inv_id,
            "transaction_id": tx_id_clean,
            "payment_status": "PAID",
            "importe_factura": float(self._quantize_half_even(invoice.get("total_factura"))),
            "importe_transaccion": float(self._quantize_half_even(tx.get("amount"))),
            "matched": True,
        }

    async def sincronizar_y_conciliar(
        self,
        *,
        empresa_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> BankSyncResult:
        """
        Persiste movimientos y ejecuta conciliaci?n autom?tica (importe + n?mero en concepto).
        """
        if not _gocardless_configured():
            raise RuntimeError("Integraci?n GoCardless no configurada en el servidor")

        n_written, _ = await self._fetch_and_store_transactions(
            empresa_id=empresa_id,
            date_from=date_from,
            date_to=date_to,
            days=90,
        )

        fresh = await _fetch_access_token()
        now = datetime.now(timezone.utc).isoformat()
        tok = _encrypt_bank_token(fresh)
        await self._db.execute(
            self._db.table("empresa_banco_sync")
            .update({"access_token_enc": tok, "updated_at": now})
            .eq("empresa_id", empresa_id)
        )

        res_inv: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id,empresa_id,total_factura,fecha_emision,estado_cobro")
            .eq("empresa_id", empresa_id)
            .in_("estado_cobro", ["pendiente", "PENDING", "pending"])
            .limit(2000)
        )
        pending_invoices: list[dict[str, Any]] = (res_inv.data or []) if hasattr(res_inv, "data") else []
        res_tx: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("transaction_id,empresa_id,amount,booked_date,reconciled")
            .eq("empresa_id", empresa_id)
            .eq("reconciled", False)
            .limit(3000)
        )
        pending_transactions: list[dict[str, Any]] = (res_tx.data or []) if hasattr(res_tx, "data") else []

        detalle = await BankingMathEngineService(self._db).match_transactions_to_invoices(
            empresa_id=empresa_id,
            pending_transactions=pending_transactions,
            pending_invoices=pending_invoices,
        )
        coincidencias = len(detalle)

        if coincidencias == 0:
            recon = ReconciliationService(self._db)
            coincidencias, detalle = await recon.auto_reconcile_invoices(empresa_id)

        return BankSyncResult(
            transacciones_procesadas=max(n_written, 0),
            coincidencias=coincidencias,
            detalle=detalle,
        )
