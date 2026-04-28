"""Seed a real Supabase Auth owner user for local smoke tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"

TARGET_EMAIL = "admin@bunker.com"
TARGET_PASSWORD = "BunkerPassword2024!"
TARGET_ROLE = "owner"


def _load_env() -> None:
    # Root first, backend env last so service credentials from backend take precedence.
    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(BACKEND_DIR / ".env", override=True)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _auth_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def _rest_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _safe_json(response: requests.Response) -> Any:
    body = (response.text or "").strip()
    if not body:
        return None
    try:
        return response.json()
    except Exception:
        return body


def _create_or_get_auth_user(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
) -> dict[str, Any]:
    users_url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    payload = {
        "email": TARGET_EMAIL,
        "password": TARGET_PASSWORD,
        "email_confirm": True,
        "user_metadata": {"role": TARGET_ROLE},
        "app_metadata": {"provider": "email", "providers": ["email"]},
    }
    response = session.post(
        users_url,
        headers=_auth_headers(service_key),
        data=json.dumps(payload),
        timeout=20,
    )
    if response.status_code < 400:
        created = _safe_json(response)
        if not isinstance(created, dict):
            raise RuntimeError(f"Invalid auth create response: {response.text[:200]}")
        return created

    # If already exists, fetch user by email from admin listing.
    list_resp = session.get(
        users_url,
        headers=_auth_headers(service_key),
        params={"page": 1, "per_page": 1000},
        timeout=20,
    )
    if list_resp.status_code >= 400:
        raise RuntimeError(
            f"Auth user create failed ({response.status_code}): {response.text}\n"
            f"Also failed listing users ({list_resp.status_code}): {list_resp.text}"
        )
    listing = _safe_json(list_resp)
    if not isinstance(listing, dict):
        raise RuntimeError(f"Unexpected auth users list response: {list_resp.text[:200]}")
    users = listing.get("users")
    if not isinstance(users, list):
        raise RuntimeError("Auth users list missing 'users' array")
    for user in users:
        if not isinstance(user, dict):
            continue
        if str(user.get("email") or "").strip().lower() == TARGET_EMAIL:
            return user
    raise RuntimeError(f"User {TARGET_EMAIL} not found after create failure: {response.text}")


def _update_profile_role_owner(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    user_id: str,
) -> list[dict[str, Any]]:
    profiles_url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    params = {"id": f"eq.{user_id}", "select": "id,email,role,empresa_id,username"}
    response = session.patch(
        profiles_url,
        headers=_rest_headers(service_key),
        params=params,
        data=json.dumps({"role": TARGET_ROLE, "email": TARGET_EMAIL}),
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"profiles update failed ({response.status_code}): {response.text}")
    rows = _safe_json(response)
    if isinstance(rows, list):
        return rows
    return []


def _read_profile(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    user_id: str,
) -> list[dict[str, Any]]:
    profiles_url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    params = {"id": f"eq.{user_id}", "select": "id,email,role,empresa_id,username", "limit": 1}
    response = session.get(
        profiles_url,
        headers=_rest_headers(service_key),
        params=params,
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"profiles read failed ({response.status_code}): {response.text}")
    rows = _safe_json(response)
    return rows if isinstance(rows, list) else []


def main() -> int:
    _load_env()
    supabase_url = _require_env("SUPABASE_URL")
    service_key = _require_env("SUPABASE_SERVICE_KEY")
    session = requests.Session()

    user = _create_or_get_auth_user(session, supabase_url, service_key)
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        raise RuntimeError("Auth user has no id")

    print("Auth user ready:")
    print(f"  id={user_id}")
    print(f"  email={TARGET_EMAIL}")

    updated_rows = _update_profile_role_owner(session, supabase_url, service_key, user_id)
    if updated_rows:
        row = updated_rows[0]
        print("Profile updated via REST:")
        print(f"  id={row.get('id')}")
        print(f"  role={row.get('role')}")
        print(f"  empresa_id={row.get('empresa_id')}")
    else:
        # Trigger may be async or profile may not exist yet; verify final state.
        rows = _read_profile(session, supabase_url, service_key, user_id)
        if not rows:
            print("WARNING: profile row not found yet (trigger may not have materialized).")
            return 0
        row = rows[0]
        print("Profile found:")
        print(f"  id={row.get('id')}")
        print(f"  role={row.get('role')}")
        print(f"  empresa_id={row.get('empresa_id')}")
        if str(row.get("role") or "").strip().lower() != TARGET_ROLE:
            raise RuntimeError("Profile role is not owner")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
