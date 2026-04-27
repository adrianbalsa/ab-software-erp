from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from app.core.mtls_certificates import (
    check_aeat_mtls_certificate_expiry,
    inspect_mtls_certificate_expiry,
)


def _build_certificate(*, expires_at: datetime) -> tuple[bytes, bytes, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AB Logistics Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "mtls-test.example"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(expires_at - timedelta(days=365))
        .not_valid_after(expires_at)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem, cert


def test_inspect_pem_certificate_warns_at_30_days(tmp_path) -> None:
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    cert_pem, key_pem, _cert = _build_certificate(expires_at=now + timedelta(days=20))
    cert_path = tmp_path / "client.pem"
    key_path = tmp_path / "client.key"
    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)

    result = inspect_mtls_certificate_expiry(
        source="settings:AEAT_CLIENT_*",
        cert_path=str(cert_path),
        key_path=str(key_path),
        now=now,
    )

    assert result["ok"] is False
    assert result["alert_level"] == "warning"
    assert result["threshold_days"] == 30
    assert result["days_remaining"] == 20
    assert result["subject_cn"] == "mtls-test.example"


def test_inspect_pem_certificate_expired_is_unhealthy(tmp_path) -> None:
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    cert_pem, key_pem, _cert = _build_certificate(expires_at=now - timedelta(days=1))
    cert_path = tmp_path / "client-expired.pem"
    key_path = tmp_path / "client-expired.key"
    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)

    result = inspect_mtls_certificate_expiry(
        source="settings:AEAT_CLIENT_*",
        cert_path=str(cert_path),
        key_path=str(key_path),
        now=now,
    )

    assert result["ok"] is False
    assert result["alert_level"] == "expired"
    assert result["threshold_days"] == 0
    assert result["days_remaining"] == -1


def test_inspect_pem_certificate_read_error_is_unhealthy(tmp_path) -> None:
    cert_path = tmp_path / "client-unreadable.pem"
    key_path = tmp_path / "client-unreadable.key"
    cert_path.write_bytes(b"not-a-certificate")
    key_path.write_bytes(b"not-a-key")

    result = inspect_mtls_certificate_expiry(
        source="settings:AEAT_CLIENT_*",
        cert_path=str(cert_path),
        key_path=str(key_path),
    )

    assert result["ok"] is False
    assert result["alert_level"] == "read_error"
    assert result["detail"].startswith("mtls_certificate_read_error:")


def test_inspect_pem_certificate_missing_is_unhealthy(tmp_path) -> None:
    key_path = tmp_path / "client.key"
    key_path.write_bytes(b"placeholder")

    result = inspect_mtls_certificate_expiry(
        source="settings:AEAT_CLIENT_*",
        cert_path=str(tmp_path / "missing-client.pem"),
        key_path=str(key_path),
    )

    assert result["ok"] is False
    assert result["alert_level"] == "missing"
    assert result["detail"] == "mtls_certificate_file_missing"


def test_inspect_p12_certificate_ok_above_30_days(tmp_path) -> None:
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    cert_pem, key_pem, cert = _build_certificate(expires_at=now + timedelta(days=60))
    key = serialization.load_pem_private_key(key_pem, password=None)
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"mtls-test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.NoEncryption(),
    )
    p12_path = tmp_path / "client.p12"
    p12_path.write_bytes(p12_bytes)

    result = inspect_mtls_certificate_expiry(
        source="settings:AEAT_CLIENT_*",
        p12_path=str(p12_path),
        now=now,
    )

    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert result["ok"] is True
    assert result["alert_level"] == "ok"
    assert result["threshold_days"] is None
    assert result["days_remaining"] == 60


@pytest.mark.asyncio
async def test_check_aeat_enabled_without_certificate_is_unhealthy(monkeypatch) -> None:
    settings = SimpleNamespace(
        AEAT_VERIFACTU_ENABLED=True,
        AEAT_CLIENT_CERT_PATH=None,
        AEAT_CLIENT_P12_PATH=None,
        AEAT_CLIENT_P12_PASSWORD=None,
    )
    monkeypatch.setattr("app.core.mtls_certificates.get_settings", lambda: settings)

    result = await check_aeat_mtls_certificate_expiry(db=None)

    assert result["ok"] is False
    assert result["skipped"] is False
    assert result["alert_thresholds_days"] == [30, 15, 7]
