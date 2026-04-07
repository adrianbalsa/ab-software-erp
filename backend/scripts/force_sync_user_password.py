#!/usr/bin/env python3
"""
One-time / utilidad: fuerza password Argon2 y vínculo empresa para un usuario en ``public.usuarios``,
y sincroniza ``profiles.role = owner`` para que el JWT lleve rbac_role=owner.

Uso (desde ``backend/`` con ``.env`` cargado):

  python scripts/force_sync_user_password.py
  python scripts/force_sync_user_password.py --empresa-id <uuid>

Requiere ``SUPABASE_SERVICE_KEY`` (o la clave de servicio que use el backend).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ENV_FILE = BACKEND_ROOT / ".env"
if ENV_FILE.exists():
    env_map = dotenv_values(ENV_FILE)
    for k, v in env_map.items():
        if k and v is not None and not os.getenv(k):
            os.environ[k] = v

from supabase import create_client  # noqa: E402

from app.core.security import hash_password_argon2id  # noqa: E402


DEFAULT_EMAIL = "adrian.balsa@yahoo.es"
DEFAULT_USERNAME = "adrian_balsa"
DEFAULT_PASSWORD = "admin123"


def _first_empresa_id(client) -> UUID:
    res = client.table("empresas").select("id").limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        raise SystemExit("No hay filas en public.empresas; crea una empresa o pasa --empresa-id.")
    raw = rows[0].get("id")
    return UUID(str(raw).strip())


def main() -> None:
    p = argparse.ArgumentParser(description="Sincroniza usuario + password Argon2 + rol owner.")
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--username", default=DEFAULT_USERNAME, help="username en usuarios si se inserta fila nueva")
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--empresa-id", dest="empresa_id", default=None, help="UUID de public.empresas")
    args = p.parse_args()

    url = os.getenv("SUPABASE_URL", "").strip()
    key = (os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("Falta SUPABASE_URL o SUPABASE_SERVICE_KEY en el entorno.")

    email = args.email.strip().lower()
    password = str(args.password)
    username = args.username.strip()

    client = create_client(url, key)
    empresa_id = UUID(args.empresa_id) if args.empresa_id else _first_empresa_id(client)
    pwd_hash = hash_password_argon2id(password)

    rows: list = []
    for qcol, qval in (
        ("email", email),
        ("email", args.email.strip()),
        ("username", username),
        ("username", email),
    ):
        try:
            res = client.table("usuarios").select("id,username,email,empresa_id").eq(qcol, qval).limit(1).execute()
            got = getattr(res, "data", None) or []
            if got:
                rows = got
                break
        except Exception:
            continue

    if not rows:
        uid = uuid4()
        insert_payload: dict = {
            "id": str(uid),
            "username": username,
            "email": email,
            "empresa_id": str(empresa_id),
            "rol": "admin",
            "password_hash": pwd_hash,
        }
        client.table("usuarios").insert(insert_payload).execute()
        print(f"Insertado usuarios.id={uid} email={email} empresa_id={empresa_id}")
        usuario_id = uid
    else:
        row = rows[0]
        usuario_id = UUID(str(row["id"]).strip())
        client.table("usuarios").update(
            {
                "email": email,
                "empresa_id": str(empresa_id),
                "password_hash": pwd_hash,
                "rol": "admin",
            }
        ).eq("id", str(usuario_id)).execute()
        print(f"Actualizado usuarios.id={usuario_id} email={email} empresa_id={empresa_id}")

    # Perfil operativo: role enum owner → JWT rbac_role owner tras login
    for filt in (
        ("id", str(usuario_id)),
        ("email", email),
    ):
        try:
            client.table("profiles").update({"role": "owner"}).eq(filt[0], filt[1]).execute()
        except Exception as exc:
            print(f"profiles.update({filt[0]}=...) omitido: {exc}")

    print("Listo. Login con ese email y la contraseña indicada; rol JWT esperado: owner.")
    print(f"  email={email}")
    print("  (password la pasada por --password)")


if __name__ == "__main__":
    main()
