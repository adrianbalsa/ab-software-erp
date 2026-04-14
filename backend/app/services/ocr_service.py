from __future__ import annotations

import datetime
import logging
import os
import re
from typing import Any

from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _parse_currency_field(field: Any) -> tuple[float, str | None]:
    """
    Azure prebuilt-invoice: montos suelen venir como CurrencyValue (amount + currency_code ISO 4217).
    """
    if field is None:
        return 0.0, None
    v = getattr(field, "value", None)
    if v is None:
        return 0.0, None

    amount = 0.0
    if hasattr(v, "amount") and v.amount is not None:
        try:
            amount = float(v.amount)
        except (TypeError, ValueError):
            amount = 0.0
    elif isinstance(v, (int, float)):
        amount = float(v)

    currency: str | None = None
    if hasattr(v, "currency_code") and v.currency_code:
        currency = str(v.currency_code).upper()[:3]

    return amount, currency


def _field_confidence(field: Any) -> float | None:
    """Azure DocumentField expone ``confidence`` en [0,1] cuando está disponible."""
    if field is None:
        return None
    c = getattr(field, "confidence", None)
    if c is None:
        return None
    try:
        return float(c)
    except (TypeError, ValueError):
        return None


def _aggregate_confidence(fields: list[Any]) -> float | None:
    vals = [c for f in fields if (c := _field_confidence(f)) is not None]
    if not vals:
        return None
    return float(min(vals))


def _invoice_date_to_iso(field: Any) -> str | None:
    if field is None or getattr(field, "value", None) is None:
        return None
    raw = field.value
    if isinstance(raw, datetime.datetime):
        return raw.date().isoformat()
    if isinstance(raw, datetime.date):
        return raw.isoformat()
    if isinstance(raw, str):
        return raw.strip()[:10]
    return None


class OCRService:
    """
    Azure Document Intelligence — modelo `prebuilt-invoice`.

    Campos usados (mapping AEAT / VeriFactu):
    - VendorName → proveedor
    - VendorTaxId → nif_proveedor
    - TotalTax → iva (cuota IVA)
    - InvoiceTotal → total + moneda (desde currency_code del importe)
    """

    def __init__(self) -> None:
        self.endpoint = os.getenv("AZURE_ENDPOINT")
        self.key = os.getenv("AZURE_KEY")

    def _get_client(self) -> DocumentAnalysisClient:
        if not self.endpoint or not self.key:
            logger.error("Faltan AZURE_ENDPOINT o AZURE_KEY en el entorno")
            raise HTTPException(
                status_code=503,
                detail="OCR no configurado: defina AZURE_ENDPOINT y AZURE_KEY.",
            )
        return DocumentAnalysisClient(self.endpoint, AzureKeyCredential(self.key))

    @staticmethod
    def limpiar_precio(texto_precio: object) -> float:
        if not texto_precio:
            return 0.0
        try:
            limpio = re.sub(r"[^\d.,]", "", str(texto_precio))
            limpio = limpio.replace(",", ".")
            partes = limpio.split(".")
            if len(partes) > 2:
                limpio = "".join(partes[:-1]) + "." + partes[-1]
            return float(limpio)
        except Exception as e:
            logger.warning("Error al limpiar precio '%s': %s", texto_precio, e)
            return 0.0

    async def analizar_ticket(self, archivo_bytes: bytes) -> dict[str, Any]:
        """
        Analiza bytes con `prebuilt-invoice` y devuelve un dict alineado con GastoOCRHint.

        Claves: proveedor, nif_proveedor, fecha (YYYY-MM-DD), total, iva, moneda, concepto.
        """
        try:
            async with self._get_client() as client:
                poller = await client.begin_analyze_document(
                    "prebuilt-invoice", document=archivo_bytes
                )
                result = await poller.result()
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Fallo en comunicación con Azure Document Intelligence")
            raise HTTPException(
                status_code=502,
                detail=f"No se pudo analizar el documento con Azure: {e!s}",
            ) from e

        if not result.documents:
            logger.warning("Azure no detectó documentos en el archivo")
            return {}

        invoice = result.documents[0]
        fields = invoice.fields or {}

        # --- Mapping explícito Azure prebuilt-invoice → negocio ---
        vendor_name = fields.get("VendorName")
        proveedor = (
            str(vendor_name.value).strip() if vendor_name and vendor_name.value else ""
        )

        vendor_tax = fields.get("VendorTaxId")
        nif_proveedor = (
            str(vendor_tax.value).strip().upper()[:20]
            if vendor_tax and vendor_tax.value
            else ""
        )

        fecha_iso = _invoice_date_to_iso(fields.get("InvoiceDate"))
        if not fecha_iso:
            fecha_iso = datetime.date.today().isoformat()

        # TotalTax → IVA (cuota) — Azure: campo TotalTax
        total_tax_field = fields.get("TotalTax")
        iva_val, _tax_ccy = _parse_currency_field(total_tax_field)
        if iva_val <= 0.0 and total_tax_field and total_tax_field.value is not None:
            tv = total_tax_field.value
            if not hasattr(tv, "amount"):
                try:
                    iva_val = float(tv)
                except (TypeError, ValueError):
                    iva_val = 0.0

        # InvoiceTotal (fallback AmountDue) → total + moneda — Azure: InvoiceTotal
        total_field = fields.get("InvoiceTotal") or fields.get("AmountDue")
        total_val, moneda = _parse_currency_field(total_field)

        if total_val <= 0.0 and total_field is not None:
            try:
                tv = getattr(total_field, "value", None)
                if tv is not None and not hasattr(tv, "amount"):
                    total_val = float(tv)
            except (TypeError, ValueError):
                pass

        if total_val <= 0.0:
            suma_items = 0.0
            items_block = fields.get("Items")
            if items_block and items_block.value:
                for item in items_block.value:
                    item_val = item.value
                    if not item_val:
                        continue
                    amt_f = item_val.get("Amount")
                    if amt_f and getattr(amt_f, "value", None) is not None:
                        sub, _ = _parse_currency_field(amt_f)
                        if sub > 0:
                            suma_items += sub
                        else:
                            suma_items += self.limpiar_precio(amt_f.value)
            total_val = suma_items + iva_val if suma_items > 0 else 0.0

        if not moneda or moneda == "":
            moneda = "EUR"

        concepto = "GASTO LOGÍSTICA"
        items_for_desc = fields.get("Items")
        if items_for_desc and items_for_desc.value:
            for it in items_for_desc.value:
                iv = it.value
                if not iv:
                    continue
                try:
                    desc_field = iv.get("Description")
                except AttributeError:
                    desc_field = getattr(iv, "Description", None)
                if desc_field and getattr(desc_field, "value", None):
                    concepto = str(desc_field.value)
                    break
        if concepto == "GASTO LOGÍSTICA" and proveedor:
            concepto = f"COMPRA EN {proveedor}"

        prov_out = proveedor.strip().upper()[:100] if proveedor.strip() else None
        nif_out = nif_proveedor.strip()[:20] if nif_proveedor.strip() else None

        conf = _aggregate_confidence(
            [
                vendor_name,
                vendor_tax,
                fields.get("InvoiceDate"),
                total_tax_field,
                total_field,
            ]
        )
        needs_review = conf is not None and conf < 0.90

        return {
            "fecha": fecha_iso,
            "proveedor": prov_out,
            "nif_proveedor": nif_out,
            "total": round(float(total_val), 2) if total_val and total_val > 0 else None,
            "iva": round(float(iva_val), 2) if iva_val and iva_val > 0 else None,
            "moneda": moneda,
            "concepto": concepto.upper().strip()[:200] if concepto else None,
            "ocr_confidence": conf,
            "requires_manual_review": needs_review,
        }
