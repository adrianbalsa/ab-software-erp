from types import SimpleNamespace

import pytest

from app.services.email_service import (
    resolve_invoice_email_channel,
    resolve_transactional_email_channel,
)


def _settings(**overrides):
    base = {
        "EMAIL_STRATEGY_INVOICE": "resend",
        "EMAIL_STRATEGY_TRANSACTIONAL": "resend",
        "RESEND_API_KEY": "re_test",
        "EMAIL_FROM_ADDRESS": "no-reply@example.com",
        "SMTP_HOST": "",
        "SMTP_PORT": 587,
        "EMAILS_FROM_EMAIL": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_invoice_strategy_auto_prefers_smtp():
    s = _settings(EMAIL_STRATEGY_INVOICE="auto", SMTP_HOST="smtp.example.com", EMAILS_FROM_EMAIL="billing@example.com")
    assert resolve_invoice_email_channel(s) == "smtp"


def test_invoice_strategy_auto_falls_back_to_resend():
    s = _settings(EMAIL_STRATEGY_INVOICE="auto")
    assert resolve_invoice_email_channel(s) == "resend"


def test_invoice_strategy_resend_requires_resend():
    s = _settings(EMAIL_STRATEGY_INVOICE="resend", RESEND_API_KEY=None)
    with pytest.raises(RuntimeError) as exc:
        resolve_invoice_email_channel(s)
    assert "resend" in str(exc.value).lower()


def test_transactional_strategy_auto_prefers_resend():
    s = _settings(
        EMAIL_STRATEGY_TRANSACTIONAL="auto",
        RESEND_API_KEY="re_test",
        SMTP_HOST="smtp.example.com",
        EMAILS_FROM_EMAIL="ops@example.com",
    )
    assert resolve_transactional_email_channel(s) == "resend"


def test_transactional_strategy_auto_falls_back_to_smtp():
    s = _settings(
        EMAIL_STRATEGY_TRANSACTIONAL="auto",
        RESEND_API_KEY=None,
        SMTP_HOST="smtp.example.com",
        EMAILS_FROM_EMAIL="ops@example.com",
    )
    assert resolve_transactional_email_channel(s) == "smtp"
