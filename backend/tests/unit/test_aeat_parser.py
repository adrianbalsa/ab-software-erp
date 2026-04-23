from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.aeat_client_py.zeep_client import RegFactuPostResult
from app.services import verifactu_sender as sender


def _map_to_factura_fields(parsed: sender.AeatEnvioResultado) -> dict[str, Any]:
    # En el modelo actual el mensaje se guarda en aeat_sif_descripcion.
    return {
        "aeat_sif_estado": parsed.estado_factura_codigo,
        "aeat_sif_csv": parsed.csv_aeat,
        "aeat_sif_mensaje": parsed.descripcion_error,
    }


def test_interpretar_respuesta_aeat_exito_total() -> None:
    xml = """
    <RespuestaRegFactu>
      <EstadoRegistro>Correcto</EstadoRegistro>
      <CSV>ABCD-1234</CSV>
    </RespuestaRegFactu>
    """
    parsed = sender.interpretar_respuesta_aeat(cuerpo=xml, http_status=200)
    mapped = _map_to_factura_fields(parsed)

    assert mapped["aeat_sif_estado"] == "aceptado"
    assert mapped["aeat_sif_csv"] == "ABCD-1234"
    assert mapped["aeat_sif_mensaje"] is None


def test_interpretar_respuesta_aeat_aceptado_con_errores() -> None:
    xml = """
    <RespuestaRegFactu>
      <EstadoRegistro>AceptadoConErrores</EstadoRegistro>
      <DescripcionErrorRegistro>Error no bloqueante en metadatos</DescripcionErrorRegistro>
      <CSV>ABCD-1234</CSV>
    </RespuestaRegFactu>
    """
    parsed = sender.interpretar_respuesta_aeat(cuerpo=xml, http_status=200)
    mapped = _map_to_factura_fields(parsed)

    assert mapped["aeat_sif_estado"] == "aceptado_con_errores"
    assert mapped["aeat_sif_csv"] == "ABCD-1234"
    assert "no bloqueante" in (mapped["aeat_sif_mensaje"] or "").lower()


def test_interpretar_respuesta_aeat_rechazo_duplicado() -> None:
    xml = """
    <RespuestaRegFactu>
      <EstadoRegistro>Rechazado</EstadoRegistro>
      <CodigoErrorRegistro>3001</CodigoErrorRegistro>
      <DescripcionErrorRegistro>Factura duplicada</DescripcionErrorRegistro>
    </RespuestaRegFactu>
    """
    parsed = sender.interpretar_respuesta_aeat(cuerpo=xml, http_status=200)
    mapped = _map_to_factura_fields(parsed)

    assert mapped["aeat_sif_estado"] == "rechazado"
    assert parsed.codigo_error == "3001"
    assert mapped["aeat_sif_csv"] is None
    assert "duplicada" in (mapped["aeat_sif_mensaje"] or "").lower()


def test_interpretar_respuesta_aeat_zeeo_tipado_desde_wsd() -> None:
    """Respuesta conforme a RespuestaRegFactuSistemaFacturacion (Zeep / AEAT)."""
    body = "<irrelevante/>"
    zres = RegFactuPostResult(
        http_status=200,
        raw_body=body,
        respuesta={
            "CSV": "ZZ99-AA",
            "EstadoEnvio": "Correcto",
            "Cabecera": {
                "ObligadoEmision": {"NombreRazon": "X", "NIF": "A0000001A"}
            },
            "TiempoEsperaEnvio": "1",
            "RespuestaLinea": [
                {
                    "EstadoRegistro": "Correcto",
                }
            ],
        },
        soap_fault=None,
    )
    parsed = sender.interpretar_respuesta_aeat(
        cuerpo=body, http_status=200, post_result=zres
    )
    assert parsed.estado_factura_codigo == "aceptado"
    assert parsed.csv_aeat == "ZZ99-AA"


def test_interpretar_respuesta_aeat_error_firma_huella() -> None:
    xml = """
    <RespuestaRegFactu>
      <EstadoRegistro>Rechazado</EstadoRegistro>
      <CodigoErrorRegistro>4102</CodigoErrorRegistro>
      <DescripcionErrorRegistro>Error validación firma XAdES y huella hash</DescripcionErrorRegistro>
    </RespuestaRegFactu>
    """
    parsed = sender.interpretar_respuesta_aeat(cuerpo=xml, http_status=200)
    mapped = _map_to_factura_fields(parsed)

    assert mapped["aeat_sif_estado"] == "rechazado"
    assert parsed.codigo_error == "4102"
    assert "xades" in (mapped["aeat_sif_mensaje"] or "").lower()
    assert "huella" in (mapped["aeat_sif_mensaje"] or "").lower()


@dataclass
class _FakeResult:
    data: list[dict[str, Any]] | None = None


class _FakeQuery:
    def __init__(self, table: str) -> None:
        self.table = table
        self.action = "select"
        self.payload: dict[str, Any] = {}
        self.filters: dict[str, Any] = {}

    def select(self, *_args: object) -> _FakeQuery:
        self.action = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "insert"
        self.payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self


class _FakeDb:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, dict[str, Any]]] = []
        self.updates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.action == "insert":
            self.inserts.append((query.table, dict(query.payload)))
            return _FakeResult(data=[dict(query.payload)])
        if query.action == "update":
            self.updates.append((query.table, dict(query.payload), dict(query.filters)))
            return _FakeResult(data=[dict(query.payload)])
        return _FakeResult(data=[])


@pytest.mark.asyncio
async def test_enviar_registro_timeout_clasifica_error_tecnico(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.aeat_client_py.exceptions import VeriFactuException

    db = _FakeDb()
    settings = SimpleNamespace(
        AEAT_VERIFACTU_ENABLED=True,
        ENVIRONMENT="development",
        AEAT_BLOQUEAR_PROD_EN_DESARROLLO=True,
        AEAT_VERIFACTU_USE_PRODUCTION=False,
        AEAT_VERIFACTU_SUBMIT_URL_TEST="https://www2.agenciatributaria.gob.es/test",
        AEAT_VERIFACTU_SUBMIT_URL_PROD=None,
        AEAT_CLIENT_KEY_PASSWORD=None,
        AEAT_VERIFACTU_WSDL_URL=None,
        AEAT_VERIFACTU_XSD_VALIDATE_REQUEST=False,
        AEAT_VERIFACTU_SUMINISTRO_LR_XSD_URL=None,
    )
    factura_row = {
        "id": 10,
        "hash_registro": "abc123",
        "fingerprint": "fp123",
        "prev_fingerprint": None,
        "num_factura": "FAC-2026-000010",
        "fecha_emision": "2026-03-27",
        "base_imponible": 100.0,
        "cuota_iva": 21.0,
        "total_factura": 121.0,
        "tipo_factura": "F1",
        "nif_emisor": "B12345678",
    }
    empresa_row = {"nif": "B12345678", "nombre_comercial": "Empresa unit test"}
    cliente = {"nif": "12345678Z", "nombre": "Cliente Test"}

    monkeypatch.setattr(
        sender,
        "_preparar_certificado_mtls",
        lambda *_args, **_kwargs: (("cert.pem", "key.pem"), []),
    )
    monkeypatch.setattr(
        sender,
        "_leer_pem_certificado_y_clave",
        lambda *_args, **_kwargs: (b"cert", b"key"),
    )
    _ns_sf = (
        "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
        "es/aeat/tike/cont/ws/SuministroInformacion.xsd"
    )

    def _stub_sign(*_a: object, **_k: object) -> bytes:
        return (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<RegistroAlta xmlns="{_ns_sf}"><IDVersion>1.0</IDVersion></RegistroAlta>'
        ).encode("utf-8")

    monkeypatch.setattr(sender, "sign_xml_xades", _stub_sign)
    monkeypatch.setattr(sender, "_limpiar_temp", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sender,
        "_post_reg_factu_soap_sync",
        lambda **_kwargs: (_ for _ in ()).throw(VeriFactuException("timeout AEAT", code="AEAT_TRANSPORT")),
    )

    out = await sender.enviar_registro_y_persistir(
        db,
        settings=settings,
        empresa_id="emp-1",
        empresa_row=empresa_row,
        factura_row=factura_row,
        cliente=cliente,
    )

    assert out.get("aeat_sif_estado") == "pendiente_envio"
    assert out.get("aeat_sif_csv") is None
    factura_updates = [
        payload
        for table, payload, _filters in db.updates
        if table == "facturas"
    ]
    assert factura_updates, "Se esperaba update sobre facturas con campos aeat_sif_*"
    aeat_sif_codigo = factura_updates[-1].get("aeat_sif_codigo")
    assert aeat_sif_codigo == "REINTENTO_AGOTADO"
    assert any(
        table == "verifactu_envios" and row.get("codigo_error") == "REINTENTO_AGOTADO"
        for table, row in db.inserts
    )
