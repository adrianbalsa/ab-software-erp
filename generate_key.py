"""
Genera una clave Fernet válida para PII_ENCRYPTION_KEY.

Uso:
  python generate_key.py
y copia el valor que imprime en tu `.env`:
  PII_ENCRYPTION_KEY="<PASTE_AQUI>"
"""

from __future__ import annotations

from cryptography.fernet import Fernet


def main() -> None:
    key = Fernet.generate_key().decode("utf-8")
    print(key)


if __name__ == "__main__":
    main()

