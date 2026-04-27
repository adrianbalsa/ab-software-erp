"""Tests Argon2id + verificación legacy SHA256 [cite: 2026-03-22]."""

from __future__ import annotations

from app.core.security import (
    hash_password_argon2id,
    password_hash_uses_legacy_sha256,
    verify_password_against_stored,
)


def test_argon2_roundtrip() -> None:
    h = hash_password_argon2id("SecretP@ssw0rd!")
    assert h.startswith("$argon2id$")
    ok, legacy = verify_password_against_stored("SecretP@ssw0rd!", h)
    assert ok is True
    assert legacy is False


def test_legacy_sha256_lazy_flag() -> None:
    # 64 hex = legacy
    legacy_hex = (
        "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"  # '123456'
    )
    ok, legacy = verify_password_against_stored("123456", legacy_hex)
    assert ok is True
    assert legacy is True
    assert password_hash_uses_legacy_sha256(legacy_hex) is True


def test_existing_argon2id_hash_still_verifies() -> None:
    existing_hash = (
        "$argon2id$v=19$m=65536,t=3,p=4$"
        "c2FsdHNhbHRzYWx0MTIzNA$"
        "eTQQXjHPlRiCcy4eOYdzQlD1FWcqKXxvEjj5I6ntdPQ"
    )
    ok, legacy = verify_password_against_stored("SecretP@ssw0rd!", existing_hash)
    assert ok is True
    assert legacy is False


def test_wrong_password() -> None:
    h = hash_password_argon2id("a")
    ok, _ = verify_password_against_stored("b", h)
    assert ok is False


def test_argon2id_no_es_legacy_sha256() -> None:
    h = hash_password_argon2id("SecretP@ssw0rd!")
    assert password_hash_uses_legacy_sha256(h) is False
