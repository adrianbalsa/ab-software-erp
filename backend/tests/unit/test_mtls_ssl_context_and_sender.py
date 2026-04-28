from __future__ import annotations

import ssl
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from app.core import mtls_certificates as mtls_module
from app.services import verifactu_sender as sender_module


class _DummySecretManager:
    def _get(self, _name: str) -> None:
        return None


def _build_certificate_bundle(*, expires_at: datetime) -> tuple[bytes, bytes, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AB Logistics Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "mtls-context-test.example"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(expires_at - timedelta(days=5))
        .not_valid_after(expires_at)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem, cert


def _to_b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def test_build_mtls_ssl_context_from_pem_base64(monkeypatch: pytest.MonkeyPatch) -> None:
    cert_pem, key_pem, _ = _build_certificate_bundle(
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    monkeypatch.setattr(mtls_module, "get_secret_manager", lambda: _DummySecretManager())
    monkeypatch.setenv("AEAT_CLIENT_CERT_PEM_B64", _to_b64(cert_pem))
    monkeypatch.setenv("AEAT_CLIENT_KEY_PEM_B64", _to_b64(key_pem))
    monkeypatch.delenv("AEAT_CLIENT_CERT_P12_B64", raising=False)

    ctx = mtls_module.build_mtls_ssl_context()

    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_build_mtls_ssl_context_from_p12_base64(monkeypatch: pytest.MonkeyPatch) -> None:
    cert_pem, key_pem, cert = _build_certificate_bundle(
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    key = serialization.load_pem_private_key(key_pem, password=None)
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"mtls-context-test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"secret"),
    )

    monkeypatch.setattr(mtls_module, "get_secret_manager", lambda: _DummySecretManager())
    monkeypatch.setenv("AEAT_CLIENT_CERT_P12_B64", _to_b64(p12_bytes))
    monkeypatch.setenv("AEAT_CLIENT_P12_PASSWORD", "secret")
    monkeypatch.delenv("AEAT_CLIENT_CERT_PEM_B64", raising=False)
    monkeypatch.delenv("AEAT_CLIENT_KEY_PEM_B64", raising=False)

    ctx = mtls_module.build_mtls_ssl_context()

    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


@pytest.mark.asyncio
async def test_send_to_aeat_logs_mock_mode_when_cert_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    settings = SimpleNamespace()
    monkeypatch.setattr(sender_module, "get_settings", lambda: settings)
    monkeypatch.setattr(sender_module, "url_envio_efectiva", lambda _settings: "https://aeat.test.local")
    monkeypatch.setattr(sender_module, "build_mtls_ssl_context", lambda: None)

    with caplog.at_level("WARNING"):
        out = await sender_module.send_to_aeat("<Factura>ok</Factura>")

    assert out["ok"] is True
    assert out["mock"] is True
    assert out["mode"] == "MODO_TEST_SIN_FIRMA"
    assert "MODO_TEST_SIN_FIRMA" in caplog.text


@pytest.mark.asyncio
async def test_send_to_aeat_uses_httpx_with_ssl_context(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace()
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200
        text = "<ok/>"

        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *, verify, timeout) -> None:
            captured["verify"] = verify
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, content: bytes, headers: dict[str, str]):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr(sender_module, "get_settings", lambda: settings)
    monkeypatch.setattr(sender_module, "url_envio_efectiva", lambda _settings: "https://aeat.test.local")
    monkeypatch.setattr(sender_module, "build_mtls_ssl_context", lambda: ssl_context)
    monkeypatch.setattr(sender_module.httpx, "AsyncClient", _FakeAsyncClient)

    out = await sender_module.send_to_aeat("<Factura>ok</Factura>")

    assert out["ok"] is True
    assert out["mock"] is False
    assert out["status_code"] == 200
    assert captured["verify"] is ssl_context
    assert captured["url"] == "https://aeat.test.local"
    assert captured["content"] == b"<Factura>ok</Factura>"
    assert captured["headers"] == {"Content-Type": "application/xml; charset=utf-8"}
