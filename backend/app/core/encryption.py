"""
Cifrado Fernet para secretos persistidos en base de datos (Open Banking, tokens, etc.).

Prioridad de clave (la primera válida gana):
1. ``ENCRYPTION_SECRET_KEY`` — recomendado en producción (44 caracteres base64, ``Fernet.generate_key().decode()``).
2. ``BANK_TOKEN_ENCRYPTION_KEY`` — compatibilidad con despliegues existentes.
3. Derivación determinista desde ``JWT_SECRET_KEY`` (solo desarrollo / legado).

Si cambia la clave usada para cifrar, los datos existentes en BD dejan de descifrarse hasta migración o reconfiguración.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    s = get_settings()
    for raw in (
        (s.ENCRYPTION_SECRET_KEY or "").strip(),
        (s.BANK_TOKEN_ENCRYPTION_KEY or "").strip(),
    ):
        if len(raw) == 44:
            try:
                return Fernet(raw.encode("ascii"))
            except Exception:
                continue
    return Fernet(
        base64.urlsafe_b64encode(
            hashlib.sha256((s.JWT_SECRET_KEY + "|abl-bank-sync-v1").encode("utf-8")).digest()
        )
    )


def encrypt_str(plain: str) -> str:
    """Cifra texto UTF-8; salida ASCII (token Fernet en base64 url-safe)."""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_str(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el dato (clave incorrecta o datos corruptos)") from exc


def encrypt_bytes(plain: bytes) -> bytes:
    return _fernet().encrypt(plain)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el dato (clave incorrecta o datos corruptos)") from exc
