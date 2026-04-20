#!/usr/bin/env python3
"""
Herramienta operativa de rotación de secretos (Due Diligence #115).

No imprime ni registra valores de claves. Genera material nuevo (Fernet) y describe
pasos para actualizar Railway / Vault / .env y **reiniciar workers**.

Auditoría opcional en Supabase (misma RPC que el backend):
  SECURITY_AUDIT_EMPRESA_ID=<uuid> + SUPABASE_URL + SUPABASE_SERVICE_KEY

Uso (desde la raíz del repo):

  python scripts/rotate_secrets.py --kind pii --dry-run
  python scripts/rotate_secrets.py --kind pii --empresa-id <uuid>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ENV_FILE = BACKEND_ROOT / ".env"
if ENV_FILE.exists():
    env_map = dotenv_values(ENV_FILE)
    for k, v in env_map.items():
        if k and v is not None and not os.getenv(k):
            os.environ[k] = v


def _audit_sync(*, empresa_id: str, secret_kind: str, success: bool, actor: str | None, detail: str) -> None:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        print("(Auditoría DB omitida: falta SUPABASE_URL o SUPABASE_SERVICE_KEY)", file=sys.stderr)
        return
    from supabase import create_client

    from app.services.security_secret_rotation_audit import log_security_secret_rotation_sync

    client = create_client(url, key)
    log_security_secret_rotation_sync(
        supabase_client=client,
        empresa_id=empresa_id,
        secret_kind=secret_kind,
        success=success,
        actor=actor,
        detail=detail,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Rotación de secretos (Stripe, GoCardless, PII Fernet, JWT).")
    p.add_argument(
        "--kind",
        required=True,
        choices=("stripe", "gocardless_pro", "gocardless_bank", "pii", "jwt"),
        help="Familia de secreto a rotar (operación manual en el proveedor + env).",
    )
    p.add_argument("--dry-run", action="store_true", help="Solo instrucciones / clave generada, sin auditoría DB.")
    p.add_argument(
        "--empresa-id",
        dest="empresa_id",
        default=os.getenv("SECURITY_AUDIT_EMPRESA_ID"),
        help="UUID tenant para audit_logs (o env SECURITY_AUDIT_EMPRESA_ID).",
    )
    p.add_argument("--actor", default=os.getenv("USER") or "cli", help="Identificador operador (sin secretos).")
    args = p.parse_args()

    detail_parts: list[str] = []
    if args.kind == "pii":
        new_key = Fernet.generate_key().decode("ascii")
        detail_parts.append("Generado nuevo Fernet (44 chars).")
        print("--- PII / Fernet ---")
        print("1. Mueva el valor actual de ENCRYPTION_KEY (o PII_ENCRYPTION_KEY) a *_PREVIOUS.")
        print("2. Asigne la nueva clave como primaria.")
        print("Nueva clave (guardar solo en gestor de secretos / Railway):")
        print(new_key)
        print("Variables sugeridas: ENCRYPTION_KEY=<nueva> y ENCRYPTION_KEY_PREVIOUS=<antigua>")
        print("  (alias PII: PII_ENCRYPTION_KEY / PII_ENCRYPTION_KEY_PREVIOUS, FERNET_PII_KEY / …)")
    elif args.kind == "stripe":
        detail_parts.append("Rotación Stripe: crear nueva restricted key en Dashboard y actualizar STRIPE_SECRET_KEY.")
        print("--- Stripe ---")
        print("1. Stripe Dashboard → Developers → API keys → crear clave restringida.")
        print("2. Actualizar STRIPE_SECRET_KEY en Railway (o Vault) y desactivar la clave antigua tras validar.")
    elif args.kind == "gocardless_pro":
        detail_parts.append("Rotación GoCardless Pro: token de acceso y reinicio de workers.")
        print("--- GoCardless Pro ---")
        print("1. GoCardless Dashboard → crear nuevo access token.")
        print("2. Actualizar GOCARDLESS_ACCESS_TOKEN en el runtime; reiniciar workers para invalidar SDK en memoria.")
    elif args.kind == "gocardless_bank":
        detail_parts.append("Rotación credenciales Bank Account Data (secret_id / secret_key).")
        print("--- GoCardless Bank Account Data ---")
        print("1. Regenerar par GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY en el portal GoCardless.")
        print("2. Actualizar variables en Railway y reiniciar.")
    else:
        detail_parts.append("Rotación JWT: invalida sesiones existentes; planificar ventana de mantenimiento.")
        print("--- JWT ---")
        print("1. Generar nuevo secreto (>= 32 bytes aleatorios).")
        print("2. Actualizar JWT_SECRET_KEY (o JWT_SECRET) y reiniciar todos los nodos a la vez.")
        print("Advertencia: todos los access tokens HS256 vigentes dejarán de ser válidos.")

    detail = " ".join(detail_parts)
    success = True

    if args.dry_run:
        print("\n(dry-run: no se escribe auditoría en base de datos)")
        return

    eid = (args.empresa_id or "").strip()
    if not eid:
        print("\n(Auditoría DB omitida: pase --empresa-id o SECURITY_AUDIT_EMPRESA_ID)", file=sys.stderr)
        return

    try:
        _audit_sync(
            empresa_id=eid,
            secret_kind=args.kind,
            success=success,
            actor=str(args.actor).strip() or None,
            detail=detail,
        )
        print("\nEvento SECURITY_SECRET_ROTATION registrado en audit_logs.", file=sys.stderr)
    except Exception as exc:
        try:
            _audit_sync(
                empresa_id=eid,
                secret_kind=args.kind,
                success=False,
                actor=str(args.actor).strip() or None,
                detail=f"Fallo al registrar auditoría: {exc}",
            )
        except Exception:
            pass
        raise SystemExit(f"Error al registrar auditoría: {exc}") from exc


if __name__ == "__main__":
    main()
