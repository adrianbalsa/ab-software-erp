from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode

# Claves típicas de query/body que no deben aparecer en logs de contenedor.
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "api_key",
        "apikey",
        "nif",
        "dni",
        "cif",
        "nie",
        "iban",
        "credit_card",
    }
)

# NIF/CIF español (aprox.) y patrones comunes en texto libre.
_NIF_LIKE = re.compile(
    r"\b\d{8}[A-HJ-NP-TV-Z]\b|\b[XYZ]\d{7}[A-HJ-NP-TV-Z]\b|\b[A-HJ-NP-SUVW][0-9]{7}[0-9A-J]\b",
    re.IGNORECASE,
)


def mask_query_string(query: str | None) -> str | None:
    """
    Enmascara valores de parámetros sensibles en query string (no altera claves no listadas).
    """
    if not query or not str(query).strip():
        return None
    pairs = parse_qsl(str(query), keep_blank_values=True)
    if not pairs:
        return None
    out: list[tuple[str, str]] = []
    for k, v in pairs:
        lk = k.lower()
        if lk in _SENSITIVE_QUERY_KEYS or any(s in lk for s in ("password", "token", "secret")):
            out.append((k, "[REDACTED]"))
        else:
            out.append((k, _mask_nif_like(v)))
    return urlencode(out)


def mask_plain_text(value: str | None, *, max_len: int = 200) -> str | None:
    """Enmascara posibles NIF/CIF en texto libre (p. ej. fragmentos de URL)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = _NIF_LIKE.sub("[NIF_REDACTED]", s)
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _mask_nif_like(value: str) -> str:
    return _NIF_LIKE.sub("[NIF_REDACTED]", value)


def mask_subject_for_log(sub: str | None) -> str | None:
    """
    Reduce huella de PII en logs: UUID o email parcialmente ocultos.
    """
    if sub is None or not str(sub).strip():
        return None
    s = str(sub).strip()
    if "@" in s:
        user, _, domain = s.partition("@")
        if len(user) <= 2:
            return f"{user[0]}***@{domain}"
        return f"{user[0]}***{user[-1]}@{domain}"
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}…{s[-4:]}"


def mask_bearer_hint(authorization: str | None) -> str:
    """Sin registrar el JWT: solo indica presencia y longitud aproximada."""
    if not authorization or not authorization.startswith("Bearer "):
        return "none"
    token = authorization[7:].strip()
    if not token:
        return "empty"
    return f"bearer(len={len(token)})"
