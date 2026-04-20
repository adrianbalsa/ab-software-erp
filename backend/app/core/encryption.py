"""
Cifrado Fernet para datos sensibles en reposo (IBAN, tokens Open Banking, etc.).

Las claves se resuelven vía ``SecretManagerService`` (multi-key decryption con
``ENCRYPTION_KEY`` + ``ENCRYPTION_KEY_PREVIOUS`` durante rotaciones).

Prioridad de clave para cifrado (primera válida de 44 caracteres base64 url-safe):
1. ``ENCRYPTION_KEY``
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
from app.services.secret_manager_service import get_secret_manager


def _fernet_from_raw(raw: str) -> Fernet | None:
    if len(raw) != 44:
        return None
    try:
        return Fernet(raw.encode("ascii"))
    except Exception:
        return None


def _fernet_instances_for_decrypt() -> list[Fernet]:
    mgr = get_secret_manager()
    keys = mgr.list_fernet_storage_raw_keys(include_previous=True)
    out: list[Fernet] = []
    for raw in keys:
        f = _fernet_from_raw(raw)
        if f is not None:
            out.append(f)
    return out


def _fernet_for_encrypt() -> Fernet:
    mgr = get_secret_manager()
    for raw in mgr.list_fernet_storage_raw_keys(include_previous=False):
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
    return _fernet_for_encrypt().encrypt(s.encode("utf-8")).decode("ascii")


def decrypt_sensitive_data(ciphertext: str | None) -> str | None:
    """
    Descifra un token Fernet. Migración suave:
    - Prueba todas las claves conocidas (actual + ``ENCRYPTION_KEY_PREVIOUS``).
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
    for f in _fernet_instances_for_decrypt():
        try:
            return f.decrypt(s.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeEncodeError):
            continue
    try:
        return _fernet_for_encrypt().decrypt(s.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError, Exception):
        return ciphertext


def encrypt_str(plain: str) -> str:
    """Cifra texto UTF-8; salida ASCII (token Fernet)."""
    return _fernet_for_encrypt().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_str(stored: str) -> str:
    for f in _fernet_instances_for_decrypt():
        try:
            return f.decrypt(stored.encode("ascii")).decode("utf-8")
        except InvalidToken:
            continue
    try:
        return _fernet_for_encrypt().decrypt(stored.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el dato (clave incorrecta o datos corruptos)") from exc


def encrypt_bytes(plain: bytes) -> bytes:
    return _fernet_for_encrypt().encrypt(plain)


def decrypt_bytes(token: bytes) -> bytes:
    for f in _fernet_instances_for_decrypt():
        try:
            return f.decrypt(token)
        except InvalidToken:
            continue
    try:
        return _fernet_for_encrypt().decrypt(token)
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el dato (clave incorrecta o datos corruptos)") from exc
