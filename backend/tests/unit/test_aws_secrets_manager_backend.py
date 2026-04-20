"""Tests de ``SECRET_MANAGER_BACKEND=aws`` (AWS Secrets Manager, mocks)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_boto3_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    sm_client = MagicMock()
    sm_client.get_secret_value.return_value = {
        "SecretString": '{"STRIPE_SECRET_KEY": " sk_aws ", "JWT_SECRET_KEY": "jwt-aws"}',
    }

    def _client(name: str, **kwargs: object) -> MagicMock:
        assert name == "secretsmanager"
        return sm_client

    monkeypatch.setattr("boto3.client", _client)
    return sm_client


def test_aws_backend_uses_secrets_manager(
    monkeypatch: pytest.MonkeyPatch,
    mock_boto3_client: MagicMock,
) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "aws")
    monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "arn:aws:secretsmanager:eu-west-1:1:secret:x")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.AwsSecretsManagerSecretManager)
    assert mgr.get_stripe_secret_key() == "sk_aws"
    assert mgr.get_jwt_secret_key() == "jwt-aws"
    mock_boto3_client.get_secret_value.assert_called_once()


def test_aws_backend_fallback_without_secret_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_MANAGER_BACKEND", "secretsmanager")
    monkeypatch.delenv("AWS_SECRETS_MANAGER_SECRET_ID", raising=False)

    from app.services import secret_manager_service as sm

    sm.reset_secret_manager()
    mgr = sm.get_secret_manager()
    assert isinstance(mgr, sm.EnvSecretManager)
