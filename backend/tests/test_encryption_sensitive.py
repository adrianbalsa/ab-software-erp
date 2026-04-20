"""Cifrado aplicación (Fernet): datos sensibles y migración suave de texto plano."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core.encryption import decrypt_sensitive_data, encrypt_sensitive_data


def test_decrypt_sensitive_multi_key_after_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tras rotar ENCRYPTION_KEY, los datos cifrados con la clave antigua siguen leyéndose."""
    from app.core.config import get_settings
    from app.services.secret_manager_service import reset_secret_manager

    key_a = Fernet.generate_key().decode("ascii")
    key_b = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("ENCRYPTION_KEY", key_a)
    monkeypatch.delenv("ENCRYPTION_KEY_PREVIOUS", raising=False)
    get_settings.cache_clear()
    reset_secret_manager()
    ciphertext = encrypt_sensitive_data("rotación-multi-clave")
    monkeypatch.setenv("ENCRYPTION_KEY", key_b)
    monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", key_a)
    get_settings.cache_clear()
    reset_secret_manager()
    assert decrypt_sensitive_data(ciphertext) == "rotación-multi-clave"


def test_encrypt_decrypt_sensitive_roundtrip() -> None:
    plain = "ES7920810038130012345678"
    enc = encrypt_sensitive_data(plain)
    assert enc is not None
    assert enc != plain
    assert enc.startswith("gAAAAA")
    assert decrypt_sensitive_data(enc) == plain


def test_decrypt_sensitive_legacy_plaintext_unchanged() -> None:
    """IBAN u otros valores guardados antes del cifrado no rompen la lectura."""
    legacy = "ES9101822466160207723053"
    assert decrypt_sensitive_data(legacy) == legacy


def test_decrypt_sensitive_invalid_token_returns_original() -> None:
    assert decrypt_sensitive_data("not-a-fernet-token") == "not-a-fernet-token"


def test_encrypt_sensitive_none_and_empty() -> None:
    assert encrypt_sensitive_data(None) is None
    assert encrypt_sensitive_data("") == ""


def test_decrypt_sensitive_none_and_empty() -> None:
    assert decrypt_sensitive_data(None) is None
    assert decrypt_sensitive_data("") == ""
