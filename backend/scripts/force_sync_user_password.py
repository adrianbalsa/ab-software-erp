#!/usr/bin/env python3
"""
Usuario maestro (owner): Argon2 en ``public.usuarios``, ``profiles.role=owner`` y ``empresa_id``.

- ``owner`` equivale a ``UserRole.ADMIN`` en la API: panel SaaS ``/api/admin/*`` y rutas
  que exigen rol de empresa (banking, export, etc.).
- Opcionalmente enlaza ``usuarios.id`` = ``auth.users.id`` (recomendado para refresh tokens)
  y hace upsert de ``profiles`` con ese ``id``.

Uso (desde ``backend/`` con ``.env`` cargado):

  python scripts/force_sync_user_password.py --email tu@correo.com --password '...'
  python scripts/force_sync_user_password.py --email tu@correo.com --password '...' --empresa-id <uuid>
  python scripts/force_sync_user_password.py --email nuevo@correo.com --password '...' --create-auth

Requiere ``SUPABASE_SERVICE_KEY``.
La contraseña debe pasarse con ``--password`` o ``FORCE_SYNC_USER_PASSWORD``
(no hay valor por defecto en el repositorio).
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


def _lookup_auth_user_id(client, *, email: str) -> str | None:
    """UUID de auth.users por email (paginado)."""
    want = email.strip().lower()
    page = 1
    while page <= 100:
        users = client.auth.admin.list_users(page=page, per_page=200)
        if not users:
            return None
        for u in users:
            uem = str(getattr(u, "email", None) or "").strip().lower()
            if uem == want:
                uid = str(getattr(u, "id", None) or "").strip()
                return uid or None
        if len(users) < 200:
            return None
        page += 1
    return None


def _first_empresa_id(client) -> UUID:
    res = client.table("empresas").select("id").limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        raise SystemExit("No hay filas en public.empresas; crea una empresa o pasa --empresa-id.")
    raw = rows[0].get("id")
    return UUID(str(raw).strip())


def main() -> None:
    p = argparse.ArgumentParser(description="Usuario maestro: usuarios + profiles owner + Argon2.")
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument(
        "--username",
        default="",
        help="Valor en public.usuarios.username (por defecto: el mismo email; recomendado para login por correo).",
    )
    p.add_argument(
        "--password",
        default=None,
        help="Contraseña en claro (obligatorio salvo FORCE_SYNC_USER_PASSWORD en entorno).",
    )
    p.add_argument("--empresa-id", dest="empresa_id", default=None, help="UUID de public.empresas")
    p.add_argument(
        "--create-auth",
        action="store_true",
        help="Si no existe en Supabase Auth, crea el usuario (email + password confirmado).",
    )
    args = p.parse_args()

    url = os.getenv("SUPABASE_URL", "").strip()
    key = (os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("Falta SUPABASE_URL o SUPABASE_SERVICE_KEY en el entorno.")

    email = args.email.strip().lower()
    password = (args.password or os.getenv("FORCE_SYNC_USER_PASSWORD") or "").strip()
    if not password:
        raise SystemExit(
            "Indique --password o defina FORCE_SYNC_USER_PASSWORD. "
            "No hay contraseña por defecto en el repositorio (Due Diligence / fugas de valor)."
        )
    password = str(password)
    username = (args.username or "").strip() or email

    client = create_client(url, key)
    empresa_id = UUID(args.empresa_id) if args.empresa_id else _first_empresa_id(client)
    pwd_hash = hash_password_argon2id(password)

    auth_uid = _lookup_auth_user_id(client, email=email)
    if auth_uid is None and args.create_auth:
        try:
            created = client.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"source": "force_sync_master_owner"},
                }
            )
            auth_uid = str(getattr(getattr(created, "user", None), "id", "") or "").strip() or None
        except Exception as exc:
            err = str(exc).lower()
            if "already been registered" in err or "already exists" in err or "duplicate" in err:
                auth_uid = _lookup_auth_user_id(client, email=email)
            else:
                raise SystemExit(f"No se pudo crear usuario en Auth: {exc}") from exc
        if not auth_uid:
            auth_uid = _lookup_auth_user_id(client, email=email)
        if auth_uid:
            print(f"Usuario Supabase Auth creado o resuelto: id={auth_uid}")
    elif auth_uid is None:
        print(
            "Aviso: no hay fila en Supabase Auth con ese email. "
            "Crea el usuario en Authentication → Users o re-ejecuta con --create-auth "
            "(usuarios.id no se alineará con auth.users y el refresh puede fallar)."
        )

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
        uid = UUID(auth_uid) if auth_uid else uuid4()
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
        if auth_uid and str(usuario_id) != auth_uid:
            print(
                f"Aviso: usuarios.id={usuario_id} ≠ auth.users.id={auth_uid}. "
                "Las cookies de refresh enlazan a usuarios.id; conviene alinear (SQL manual o nueva cuenta). "
                "Se actualiza password/empresa en la fila existente."
            )
        client.table("usuarios").update(
            {
                "username": username,
                "email": email,
                "empresa_id": str(empresa_id),
                "password_hash": pwd_hash,
                "rol": "admin",
            }
        ).eq("id", str(usuario_id)).execute()
        print(f"Actualizado usuarios.id={usuario_id} email={email} empresa_id={empresa_id}")

    # Perfil: owner + empresa (upsert si conocemos auth id; si no, solo role por email/id usuarios)
    profile_payload = {
        "email": email,
        "username": username,
        "empresa_id": str(empresa_id),
        "role": "owner",
        "rol": "admin",
    }
    if auth_uid:
        profile_payload["id"] = auth_uid
        try:
            client.table("profiles").upsert(profile_payload, on_conflict="id").execute()
            print(f"profiles upsert id={auth_uid} role=owner empresa_id={empresa_id}")
        except Exception as exc:
            print(f"profiles.upsert omitido: {exc}; intentando update por email.")
            for filt in (("id", str(usuario_id)), ("email", email)):
                try:
                    client.table("profiles").update({"role": "owner", "empresa_id": str(empresa_id)}).eq(
                        filt[0], filt[1]
                    ).execute()
                except Exception as exc2:
                    print(f"profiles.update({filt[0]}=…) omitido: {exc2}")
    else:
        for filt in (
            ("id", str(usuario_id)),
            ("email", email),
        ):
            try:
                client.table("profiles").update(
                    {"role": "owner", "empresa_id": str(empresa_id), "username": username}
                ).eq(filt[0], filt[1]).execute()
            except Exception as exc:
                print(f"profiles.update({filt[0]}=...) omitido: {exc}")

    print("Listo. Login en la app con el username indicado (por defecto el email) y la contraseña.")
    print("  Rol operativo: owner (acceso amplio de empresa + rutas admin con UserRole.ADMIN).")
    print(f"  email={email} username={username}")


if __name__ == "__main__":
    main()
