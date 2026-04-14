"""Validación opcional de peticiones contra XSD oficiales AEAT (xmlschema)."""

from __future__ import annotations

from functools import lru_cache
from typing import Final

import xmlschema
from defusedxml import ElementTree as DefusedET

_NS_SUMINISTRO_LR: Final = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroLR.xsd"
)


@lru_cache(maxsize=8)
def _schema_suministro_lr(location: str) -> xmlschema.XMLSchema:
    return xmlschema.XMLSchema(location)


def validate_reg_factu_payload_against_suministro_lr_xsd(
    *,
    reg_factu_inner_xml: str,
    schema_location: str,
) -> None:
    """
    Valida el fragmento que va bajo ``RegFactuSistemaFacturacion`` respecto al
    XSD **SuministroLR** (elemento complejo con ``Cabecera`` + ``RegistroFactura``).

    El fragmento debe seguir **SuministroLR** (``Cabecera`` + ``RegistroFactura`` con
    ``RegistroAlta`` firmado cuando proceda). El esquema por defecto es el XSD local
    empaquetado en ``aeat_client_py/xsd/``.
    """
    inner = (reg_factu_inner_xml or "").strip()
    if inner.startswith("<?xml"):
        raise ValueError("reg_factu_inner_xml no debe incluir la declaración XML")
    wrapped = (
        f'<ns:RegFactuSistemaFacturacion xmlns:ns="{_NS_SUMINISTRO_LR}">{inner}</ns:RegFactuSistemaFacturacion>'
    )
    schema = _schema_suministro_lr(schema_location)
    schema.validate(wrapped)


def assert_well_formed_xml(data: bytes) -> None:
    """Parse defensivo (sin entidades externas)."""
    DefusedET.fromstring(data)
