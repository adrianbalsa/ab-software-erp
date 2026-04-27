"""Resolucion de hash genesis VeriFactu por emisor (Secret Manager, sin fallback en codigo)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import ConfigError
from app.services import secret_manager_service as sm


def test_get_verifactu_genesis_hash_for_issuer_from_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    h = "c" * 64
    monkeypatch.setenv("VERIFACTU_GENESIS_HASHES", '{"empresa-alpha": "' + h + '"}')
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import get_verifactu_genesis_hash_for_issuer

    assert get_verifactu_genesis_hash_for_issuer(issuer_id="empresa-alpha") == h


def test_get_verifactu_genesis_hash_for_issuer_single_global_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    monkeypatch.delenv("VERIFACTU_GENESIS_HASHES", raising=False)
    h = "d" * 64
    monkeypatch.setenv("VERIFACTU_GENESIS_HASH", h)
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import get_verifactu_genesis_hash_for_issuer

    assert get_verifactu_genesis_hash_for_issuer(issuer_id="cualquier-emisor-uuid") == h


def test_get_verifactu_genesis_hash_for_issuer_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    monkeypatch.delenv("VERIFACTU_GENESIS_HASHES", raising=False)
    monkeypatch.delenv("VERIFACTU_GENESIS_HASH", raising=False)
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import get_verifactu_genesis_hash_for_issuer

    with pytest.raises(RuntimeError, match="verifactu_genesis_hash_missing_for_issuer"):
        get_verifactu_genesis_hash_for_issuer(issuer_id="sin-config")


def test_assert_production_aeat_skips_when_not_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    monkeypatch.delenv("VERIFACTU_GENESIS_HASHES", raising=False)
    monkeypatch.delenv("VERIFACTU_GENESIS_HASH", raising=False)
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import assert_verifactu_genesis_configured_for_production_aeat

    assert_verifactu_genesis_configured_for_production_aeat(
        SimpleNamespace(ENVIRONMENT="development", AEAT_VERIFACTU_ENABLED=True)
    )


def test_assert_production_aeat_skips_when_aeat_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    monkeypatch.delenv("VERIFACTU_GENESIS_HASHES", raising=False)
    monkeypatch.delenv("VERIFACTU_GENESIS_HASH", raising=False)
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import assert_verifactu_genesis_configured_for_production_aeat

    assert_verifactu_genesis_configured_for_production_aeat(
        SimpleNamespace(ENVIRONMENT="production", AEAT_VERIFACTU_ENABLED=False)
    )


def test_assert_production_aeat_raises_config_error_without_genesis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    monkeypatch.delenv("VERIFACTU_GENESIS_HASHES", raising=False)
    monkeypatch.delenv("VERIFACTU_GENESIS_HASH", raising=False)
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import assert_verifactu_genesis_configured_for_production_aeat

    with pytest.raises(ConfigError, match="VERIFACTU_GENESIS_HASH"):
        assert_verifactu_genesis_configured_for_production_aeat(
            SimpleNamespace(ENVIRONMENT="production", AEAT_VERIFACTU_ENABLED=True)
        )


def test_assert_production_aeat_ok_with_global_genesis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "env")
    monkeypatch.delenv("VERIFACTU_GENESIS_HASHES", raising=False)
    monkeypatch.setenv("VERIFACTU_GENESIS_HASH", "e" * 64)
    sm.reset_secret_manager()

    from app.services.verifactu_genesis import assert_verifactu_genesis_configured_for_production_aeat

    assert_verifactu_genesis_configured_for_production_aeat(
        SimpleNamespace(ENVIRONMENT="production", AEAT_VERIFACTU_ENABLED=True)
    )
