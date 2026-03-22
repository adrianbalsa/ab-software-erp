"""Tests Argon2id + verificación legacy SHA256 [cite: 2026-03-22]."""

from __future__ import annotations

from app.core.security import (
    hash_password_argon2id,
    verify_password_against_stored,
)


def test_argon2_roundtrip() -> None:
    h = hash_password_argon2id("SecretP@ssw0rd!")
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


def test_wrong_password() -> None:
    h = hash_password_argon2id("a")
    ok, _ = verify_password_against_stored("b", h)
    assert ok is False
