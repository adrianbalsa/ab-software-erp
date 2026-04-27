from __future__ import annotations

import re
from typing import Any, Mapping

from app.core.verifactu_hashing import (
    VerifactuCadena,
    generar_hash_factura_oficial,
)
from app.services.aeat_client_py.xsd_validate import validate_reg_factu_payload_against_suministro_lr_xsd
from app.services.aeat_client_py.zeep_client import default_aeat_suministro_lr_xsd_url
from app.services.suministro_lr_xml import RegistroAnteriorAEAT, fecha_iso_u_otra_a_dd_mm_yyyy
from app.services.verifactu_genesis import get_verifactu_genesis_hash_for_issuer
from app.services.verifactu_sender import generar_xml_registro_facturacion_alta


class VeriFactuXmlService:
    """
    Generador XML VeriFactu (estructura SuministroLR / RegFactu).

    Recibe una factura ya calculada por Math Engine y aplica el encadenamiento
    de huellas para producir el payload XML listo para firma/envío.
    """

    def build_invoice_xml(
        self,
        *,
        factura: Mapping[str, Any],
        empresa: Mapping[str, Any],
        cliente: Mapping[str, Any],
        previous_fingerprint: str | None = None,
        previous_invoice: Mapping[str, Any] | None = None,
    ) -> str:
        previous = str(previous_fingerprint or "").strip()
        if not previous:
            previous = get_verifactu_genesis_hash_for_issuer(
                issuer_id=str(empresa.get("id") or factura.get("empresa_id") or ""),
                issuer_nif=str(empresa.get("nif") or factura.get("nif_emisor") or ""),
            )
        hash_registro = generar_hash_factura_oficial(
            VerifactuCadena.HUELLA_EMISION,
            dict(factura),
            previous,
        )
        fingerprint = generar_hash_factura_oficial(
            VerifactuCadena.HUELLA_FINGERPRINT,
            dict(factura),
            previous,
        )

        registro_anterior: RegistroAnteriorAEAT | None = None
        if previous_fingerprint:
            if previous_invoice is None:
                raise ValueError("Debe proporcionar previous_invoice cuando exista previous_fingerprint.")
            registro_anterior = RegistroAnteriorAEAT(
                id_emisor_factura=str(
                    previous_invoice.get("nif_emisor")
                    or previous_invoice.get("id_emisor")
                    or empresa.get("nif")
                    or ""
                ).strip(),
                num_serie_factura=str(
                    previous_invoice.get("num_factura")
                    or previous_invoice.get("numero_factura")
                    or ""
                ).strip(),
                fecha_expedicion=fecha_iso_u_otra_a_dd_mm_yyyy(
                    str(previous_invoice.get("fecha_emision") or "")
                ),
                huella=str(previous_fingerprint).strip(),
            )

        xml = generar_xml_registro_facturacion_alta(
            factura=factura,
            empresa=empresa,
            cliente=cliente,
            hash_registro=hash_registro,
            fingerprint=fingerprint,
            prev_fingerprint=(str(previous_fingerprint).strip() if previous_fingerprint is not None else None),
            registro_anterior=registro_anterior,
            rectificada=None,
        )
        return xml

    def validate_against_regfactu_schema(self, xml_content: str) -> None:
        """
        Valida el XML interior RegFactu contra el XSD de SuministroLR empaquetado.
        """
        inner = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml_content.strip(), count=1)
        validate_reg_factu_payload_against_suministro_lr_xsd(
            reg_factu_inner_xml=inner,
            schema_location=default_aeat_suministro_lr_xsd_url(),
        )
