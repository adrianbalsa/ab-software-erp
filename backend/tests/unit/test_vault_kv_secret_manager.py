"""Tests del backend HashiCorp Vault KV v2 (`SecretManagerService`)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hvac.exceptions import Forbidden


@pytest.fixture
def vault_hvac_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    client_inst = MagicMock()
    client_inst.secrets.kv.v2.read_secret_version.return_value = {
        "data": {
            "data": {
                "STRIPE_SECRET_KEY": " sk_test ",
                "JWT_SECRET_KEY": "jwt-from-vault",
                "GOCARDLESS_ENV": "live",
            },
        },
    }

    def _client_factory(**kwargs: object) -> MagicMock:
        return client_inst

    monkeypatch.setattr("app.services.secret_manager_service.hvac.Client", _client_factory)
    return client_inst


def test_vault_backend_fallback_env_without_addr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "vault")
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_KV_PATH", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    from app.services.secret_manager_service import SaaSEnvSecretProvider, get_secret_manager, reset_secret_manager

    reset_secret_manager()
    mgr = get_secret_manager()
    assert isinstance(mgr, SaaSEnvSecretProvider)


def test_vault_backend_uses_kv_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    vault_hvac_client: MagicMock,
) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "vault")
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example:8200")
    monkeypatch.setenv("VAULT_KV_PATH", "scanner/prod")
    monkeypatch.setenv("VAULT_KV_MOUNT", "kv")
    monkeypatch.setenv("VAULT_TOKEN", "dev-root")
    monkeypatch.delenv("VAULT_TOKEN_FILE", raising=False)

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.VaultKvSecretManager)

    assert mgr.get_stripe_secret_key() == "sk_test"
    assert mgr.get_jwt_secret_key() == "jwt-from-vault"
    assert mgr.get_gocardless_env() == "live"

    vault_hvac_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
        path="scanner/prod",
        mount_point="kv",
    )

    _ = mgr.get_stripe_secret_key()
    assert vault_hvac_client.secrets.kv.v2.read_secret_version.call_count == 1

    sm.bump_integration_secret_version()
    _ = mgr.get_stripe_secret_key()
    assert vault_hvac_client.secrets.kv.v2.read_secret_version.call_count == 2


def test_vault_token_file(
    monkeypatch: pytest.MonkeyPatch,
    vault_hvac_client: MagicMock,
    tmp_path,
) -> None:
    tok = tmp_path / "vault-token"
    tok.write_text("  from-file-token  \n", encoding="utf-8")

    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "vault")
    monkeypatch.setenv("VAULT_ADDR", "https://vault:8200")
    monkeypatch.setenv("VAULT_KV_PATH", "app/x")
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    monkeypatch.setenv("VAULT_TOKEN_FILE", str(tok))

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.VaultKvSecretManager)
    assert mgr.get_stripe_secret_key() == "sk_test"


def test_vault_kubernetes_auth(
    monkeypatch: pytest.MonkeyPatch,
    vault_hvac_client: MagicMock,
    tmp_path,
) -> None:
    jwt = tmp_path / "k8s.jwt"
    jwt.write_text("fake-jwt-token-for-vault", encoding="utf-8")

    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "vault")
    monkeypatch.setenv("VAULT_ADDR", "https://vault:8200")
    monkeypatch.setenv("VAULT_KV_PATH", "app/k8s")
    monkeypatch.setenv("VAULT_AUTH_METHOD", "kubernetes")
    monkeypatch.setenv("VAULT_K8S_ROLE", "scanner-api")
    monkeypatch.setenv("VAULT_K8S_JWT_PATH", str(jwt))
    monkeypatch.delenv("VAULT_TOKEN", raising=False)

    vault_hvac_client.auth.kubernetes.login.return_value = {"auth": {"client_token": "sess"}}

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.VaultKvSecretManager)
    assert mgr.get_stripe_secret_key() == "sk_test"
    vault_hvac_client.auth.kubernetes.login.assert_called_once_with(
        role="scanner-api",
        jwt="fake-jwt-token-for-vault",
    )


def test_vault_approle_auth(
    monkeypatch: pytest.MonkeyPatch,
    vault_hvac_client: MagicMock,
    tmp_path,
) -> None:
    sid = tmp_path / "secret_id"
    sid.write_text("wrapped-secret-id\n", encoding="utf-8")

    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "vault")
    monkeypatch.setenv("VAULT_ADDR", "https://vault:8200")
    monkeypatch.setenv("VAULT_KV_PATH", "app/role")
    monkeypatch.setenv("VAULT_AUTH_METHOD", "approle")
    monkeypatch.setenv("VAULT_APPROLE_ROLE_ID", "role-id-hex")
    monkeypatch.delenv("VAULT_APPROLE_SECRET_ID", raising=False)
    monkeypatch.setenv("VAULT_APPROLE_SECRET_ID_FILE", str(sid))

    vault_hvac_client.auth.approle.login.return_value = {"auth": {"client_token": "sess2"}}

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.VaultKvSecretManager)
    assert mgr.get_stripe_secret_key() == "sk_test"
    vault_hvac_client.auth.approle.login.assert_called_once_with(
        role_id="role-id-hex",
        secret_id="wrapped-secret-id",
    )


def test_vault_kv_retries_on_forbidden(
    monkeypatch: pytest.MonkeyPatch,
    vault_hvac_client: MagicMock,
) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "vault")
    monkeypatch.setenv("VAULT_ADDR", "https://vault:8200")
    monkeypatch.setenv("VAULT_KV_PATH", "p")
    monkeypatch.setenv("VAULT_TOKEN", "t")

    vault_hvac_client.secrets.kv.v2.read_secret_version.side_effect = [
        Forbidden(),
        {
            "data": {
                "data": {
                    "STRIPE_SECRET_KEY": "after-reauth",
                    "JWT_SECRET_KEY": "jwt-from-vault",
                    "GOCARDLESS_ENV": "live",
                },
            },
        },
    ]

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.VaultKvSecretManager)
    assert mgr.get_stripe_secret_key() == "after-reauth"
    assert vault_hvac_client.secrets.kv.v2.read_secret_version.call_count == 2
