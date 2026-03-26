"""
Cifrado Fernet para datos sensibles en reposo (IBAN, tokens Open Banking, etc.).

Prioridad de clave (`Fernet`, 44 caracteres base64 url-safe):
1. ``ENCRYPTION_KEY`` — recomendado (Fase 1 Data Security).
2. ``ENCRYPTION_SECRET_KEY``
3. ``BANK_TOKEN_ENCRYPTION_KEY``
4. Derivación determinista desde ``JWT_SECRET_KEY`` (solo desarrollo / legado sin clave explícita)

- ``encrypt_sensitive_data`` / ``decrypt_sensitive_data``: API para PII financiero; el descifrado es **tolerante**
  (texto plano legacy o token inválido → se devuelve el valor original).
- ``encrypt_str`` / ``decrypt_str``: integridad estricta en flujos bancarios (``decrypt_str`` lanza si falla).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _raw_key_candidates() -> tuple[str, ...]:
    s = get_settings()
    return (
        (s.ENCRYPTION_KEY or "").strip(),
        (s.ENCRYPTION_SECRET_KEY or "").strip(),
        (s.BANK_TOKEN_ENCRYPTION_KEY or "").strip(),
    )


def _fernet_from_raw(raw: str) -> Fernet | None:
    if len(raw) != 44:
        return None
    try:
        return Fernet(raw.encode("ascii"))
    except Exception:
        return None


def _fernet() -> Fernet:
    """Instancia Fernet para operaciones estándar (primera clave válida)."""
    for raw in _raw_key_candidates():
        f = _fernet_from_raw(raw)
        if f is not None:
            return f
    s = get_settings()
    return Fernet(
        base64.urlsafe_b64encode(
            hashlib.sha256((s.JWT_SECRET_KEY + "|abl-bank-sync-v1").encode("utf-8")).digest()
        )
    )


def encrypt_sensitive_data(plain: str | None) -> str | None:
    """
    Cifra un campo sensible antes de persistirlo.
    ``None`` se mantiene; cadena vacía no se cifra.
    """
    if plain is None:
        return None
    s = str(plain).strip()
    if not s:
        return ""
    return _fernet().encrypt(s.encode("utf-8")).decode("ascii")


def decrypt_sensitive_data(ciphertext: str | None) -> str | None:
    """
    Descifra un token Fernet. Migración suave:
    - Token inválido, clave incorrecta o **datos legacy en claro** → devuelve el texto original (sin excepción).
    - ``None`` → ``None``.
    """
    if ciphertext is None:
        return None
    if not isinstance(ciphertext, str):
        return str(ciphertext)
    s = ciphertext.strip()
    if not s:
        return ""
    try:
        return _fernet().decrypt(s.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError, Exception):
        return ciphertext


def encrypt_str(plain: str) -> str:
    """Cifra texto UTF-8; salida ASCII (token Fernet)."""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_str(stored: str) -> str:
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el dato (clave incorrecta o datos corruptos)") from exc


def encrypt_bytes(plain: bytes) -> bytes:
    return _fernet().encrypt(plain)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el dato (clave incorrecta o datos corruptos)") from exc
