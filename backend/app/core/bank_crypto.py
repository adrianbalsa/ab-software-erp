"""
Compatibilidad: re-exporta el cifrado unificado desde ``app.core.encryption``.
"""

from __future__ import annotations

from app.core.encryption import decrypt_str, encrypt_str

__all__ = ["decrypt_str", "encrypt_str"]
