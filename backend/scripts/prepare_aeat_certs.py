#!/usr/bin/env python3
"""
Extrae certificado y clave privada desde un PKCS#12 (.p12/.pfx) para mTLS AEAT.

Uso:
  python scripts/prepare_aeat_certs.py --p12 /ruta/certificate.p12 --password "secret"

Si no se pasa --password, usa AEAT_CLIENT_P12_PASSWORD del entorno.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12


def _chmod_owner_only(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _validate_input_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No existe el fichero PKCS#12: {path}")
    if not path.is_file():
        raise ValueError(f"La ruta PKCS#12 no es un archivo: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extrae cert.pem y key.pem desde un PKCS#12 para AEAT.")
    parser.add_argument("--p12", required=True, help="Ruta al archivo .p12/.pfx")
    parser.add_argument("--password", default=None, help="Password del PKCS#12 (opcional)")
    parser.add_argument(
        "--out-dir",
        default="backend/certs",
        help="Directorio de salida para PEM (default: backend/certs)",
    )
    args = parser.parse_args(argv)

    p12_path = Path(args.p12).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    password_text = args.password if args.password is not None else os.getenv("AEAT_CLIENT_P12_PASSWORD")
    password_bytes = password_text.encode("utf-8") if password_text else None

    try:
        _validate_input_file(p12_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        raw = p12_path.read_bytes()
        private_key, certificate, extra_certs = pkcs12.load_key_and_certificates(raw, password_bytes)
        if private_key is None or certificate is None:
            raise ValueError("El PKCS#12 no contiene clave privada y certificado válidos.")

        cert_path = out_dir / "aeat_client_cert.pem"
        key_path = out_dir / "aeat_client_key.pem"
        chain_path = out_dir / "aeat_client_chain.pem"

        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        _chmod_owner_only(cert_path)
        _chmod_owner_only(key_path)

        if extra_certs:
            chain_pem = b"".join(c.public_bytes(serialization.Encoding.PEM) for c in extra_certs)
            chain_path.write_bytes(chain_pem)
            _chmod_owner_only(chain_path)

        print("Certificados AEAT preparados correctamente.")
        print(f"- Certificado: {cert_path}")
        print(f"- Clave privada: {key_path}")
        if extra_certs:
            print(f"- Cadena intermedia: {chain_path}")
        print("")
        print("Sugerencia .env:")
        print(f'AEAT_CLIENT_CERT_PATH="{cert_path}"')
        print(f'AEAT_CLIENT_KEY_PATH="{key_path}"')
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR preparando certificados AEAT: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
