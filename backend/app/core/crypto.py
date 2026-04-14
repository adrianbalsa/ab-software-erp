"""
PII encryption in-app (Zero Trust en reposo).

La implementación vive en ``app.core.security`` (Fernet); este módulo conserva ``pii_crypto``
para imports existentes en servicios y rutas.
"""

from __future__ import annotations

from app.core.security import fernet_decrypt_string, fernet_encrypt_string


class PiiCrypto:
    def encrypt_pii(self, plain_text: str | None) -> str | None:
        return fernet_encrypt_string(plain_text)

    def decrypt_pii(self, cipher_text: str | None) -> str | None:
        return fernet_decrypt_string(cipher_text)


pii_crypto = PiiCrypto()
