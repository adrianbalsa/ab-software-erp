"""Utilidades para reducir PII en breadcrumbs de Sentry (defensa en profundidad)."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_FRAGMENTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "auth",
    "cookie",
    "set-cookie",
    "email",
    "mail",
    "phone",
    "mobile",
    "iban",
    "nif",
    "dni",
    "cif",
    "ssn",
    "credit",
    "card",
    "cvv",
)

_EMAIL_LIKE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _key_looks_sensitive(key: str) -> bool:
    k = key.lower().replace("-", "_")
    return any(s in k for s in _SENSITIVE_KEY_FRAGMENTS)


def redact_pii_structure(value: Any, depth: int = 0) -> Any:
    """Recorre dict/list/tuple y sustituye valores bajo claves sensibles o emails en strings."""
    if depth > 12:
        return "[Truncated]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            ks = str(k)
            if _key_looks_sensitive(ks):
                out[ks] = "[Filtered]"
            else:
                out[ks] = redact_pii_structure(v, depth + 1)
        return out
    if isinstance(value, list):
        return [redact_pii_structure(x, depth + 1) for x in value]
    if isinstance(value, tuple):
        return tuple(redact_pii_structure(x, depth + 1) for x in value)
    if isinstance(value, str):
        if _EMAIL_LIKE.search(value):
            return _EMAIL_LIKE.sub("[email]", value)
        return value
    return value


def scrub_sentry_breadcrumb(crumb: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Callback ``before_breadcrumb``: evita PII en datos adjuntos al crumb."""
    data = crumb.get("data")
    if isinstance(data, dict):
        crumb = {**crumb, "data": redact_pii_structure(data)}
    message = crumb.get("message")
    if isinstance(message, str) and _EMAIL_LIKE.search(message):
        crumb = {**crumb, "message": _EMAIL_LIKE.sub("[email]", message)}
    return crumb
