"""Cifrado aplicación (Fernet): datos sensibles y migración suave de texto plano."""

from __future__ import annotations

from app.core.encryption import decrypt_sensitive_data, encrypt_sensitive_data


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
