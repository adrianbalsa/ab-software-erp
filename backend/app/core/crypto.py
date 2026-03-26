"""
PII encryption in-app (Zero Trust en reposo).

Implementa cifrado simétrico con Fernet para campos sensibles (IBAN/NIF, etc.).

Fuente de clave:
- `PII_ENCRYPTION_KEY` (recomendado; 44 caracteres base64 url-safe).
- Fallback: `app.core.encryption` (compatibilidad legacy) si falta PII_ENCRYPTION_KEY.
"""

from __future__ import annotations

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.encryption import decrypt_sensitive_data, encrypt_sensitive_data


def _get_raw_key_from_env() -> Optional[str]:
    raw = (os.getenv("PII_ENCRYPTION_KEY") or "").strip()
    # Fernet keys are always 44 chars base64 url-safe
    if len(raw) != 44:
        return None
    return raw


class PiiCrypto:
    def __init__(self) -> None:
        raw = _get_raw_key_from_env()
        self._fernet: Fernet | None = Fernet(raw.encode("ascii")) if raw else None

    @staticmethod
    def _maybe_already_encrypted(value: str) -> bool:
        # Fernet tokens typically start with "gAAAA".
        return value.startswith("gAAAA")

    def encrypt_pii(self, plain_text: str | None) -> str | None:
        if plain_text is None:
            return None
        s = str(plain_text).strip()
        if s == "":
            return ""

        # Idempotencia suave: si parece token Fernet, no volvemos a cifrar.
        if self._maybe_already_encrypted(s):
            return s

        if self._fernet is None:
            # Compatibilidad con despliegues existentes.
            return encrypt_sensitive_data(s)

        token = self._fernet.encrypt(s.encode("utf-8")).decode("ascii")
        return token

    def decrypt_pii(self, cipher_text: str | None) -> str | None:
        if cipher_text is None:
            return None
        if not isinstance(cipher_text, str):
            return str(cipher_text)

        s = cipher_text.strip()
        if s == "":
            return ""

        if self._fernet is not None:
            try:
                return self._fernet.decrypt(s.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError):
                pass

        # Fallback: descifrado tolerante legacy (si ya estaba cifrado con ENCRYPTION_KEY).
        dec = decrypt_sensitive_data(s)
        return dec


# Singleton: usarlo desde services/rutas.
pii_crypto = PiiCrypto()

