from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID
from uuid import uuid4

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
SEED_OUTPUT_PATH = ROOT / "tests" / ".smoke_seed_ids.json"


def _load_env() -> None:
    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(BACKEND_DIR / ".env", override=False)


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _sb_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def _safe_json(res: requests.Response) -> Any:
    body = (res.text or "").strip()
    if not body:
        return None
    return res.json()


def _is_uuid(value: object) -> bool:
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


def _select_profiles(session: requests.Session, supabase_url: str, service_key: str) -> list[dict[str, Any]]:
    url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    for select_fields in (
        "id,empresa_id,email,username,role,rol",
        "id,empresa_id,email,username,role",
        "id,empresa_id,email,role",
    ):
        params = {
            "select": select_fields,
            "limit": "1000",
        }
        res = session.get(url, headers=_sb_headers(service_key), params=params, timeout=20)
        if res.status_code < 400:
            data = _safe_json(res)
            return data if isinstance(data, list) else []
    raise RuntimeError(f"profiles select failed ({res.status_code}): {res.text}")


def _pick_empresa_id(profiles: list[dict[str, Any]]) -> str:
    for profile in profiles:
        value = profile.get("empresa_id")
        if _is_uuid(value):
            return str(value)
    raise RuntimeError("No valid empresa_id found in profiles")


def _is_admin_role(profile: dict[str, Any]) -> bool:
    role = str(profile.get("role") or "").strip().lower()
    return role in {"admin", "superadmin", "developer", "owner"}


def _is_driver_role(profile: dict[str, Any]) -> bool:
    role = str(profile.get("role") or "").strip().lower()
    return role in {"driver", "transportista"}


def _update_profile(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    profile_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    params = {"id": f"eq.{profile_id}", "select": "id,empresa_id,email,username,role"}
    res = session.patch(url, headers=_sb_headers(service_key), params=params, json=payload, timeout=20)
    if res.status_code >= 400:
        raise RuntimeError(f"profiles update failed ({res.status_code}): {res.text}")
    rows = _safe_json(res)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"profiles update returned no rows for id={profile_id}")
    return rows[0]


def _insert_profile(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    params = {"select": "id,empresa_id,email,username,role"}
    res = session.post(url, headers=_sb_headers(service_key), params=params, json=payload, timeout=20)
    if res.status_code >= 400:
        raise RuntimeError(f"profiles insert failed ({res.status_code}): {res.text}")
    rows = _safe_json(res)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("profiles insert returned no rows")
    return rows[0]


def _select_profile_by_id(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    profile_id: str,
) -> dict[str, Any] | None:
    url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    params = {
        "select": "id,empresa_id,email,username,role",
        "id": f"eq.{profile_id}",
        "limit": "1",
    }
    res = session.get(url, headers=_sb_headers(service_key), params=params, timeout=20)
    if res.status_code >= 400:
        raise RuntimeError(f"profiles by id select failed ({res.status_code}): {res.text}")
    rows = _safe_json(res)
    if not isinstance(rows, list) or not rows:
        return None
    return rows[0]


def _create_auth_user(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    *,
    email: str,
) -> str:
    url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    payload = {
        "email": email,
        "email_confirm": True,
        "user_metadata": {"source": "smoke_security_seed"},
        "app_metadata": {"provider": "email", "providers": ["email"]},
    }
    res = session.post(
        url,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if res.status_code >= 400:
        raise RuntimeError(f"auth user create failed ({res.status_code}): {res.text}")
    body = _safe_json(res)
    if not isinstance(body, dict):
        raise RuntimeError(f"auth user create returned invalid body: {res.text[:200]}")
    user_id = str(body.get("id") or "").strip()
    if not _is_uuid(user_id):
        raise RuntimeError("auth user create response missing valid id")
    return user_id


def _ensure_admin_and_driver(
    session: requests.Session,
    supabase_url: str,
    service_key: str,
    profiles: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    empresa_id = _pick_empresa_id(profiles)
    valid_profiles = [p for p in profiles if _is_uuid(p.get("id"))]
    if not valid_profiles:
        raise RuntimeError("No valid profile IDs found to seed test data")

    admin_profile = next((p for p in valid_profiles if _is_admin_role(p)), None)
    driver_profile = next((p for p in valid_profiles if _is_driver_role(p)), None)

    if admin_profile is None:
        admin_profile = _update_profile(
            session=session,
            supabase_url=supabase_url,
            service_key=service_key,
            profile_id=str(valid_profiles[0]["id"]),
            payload={"role": "admin", "empresa_id": empresa_id},
        )
    if driver_profile is None:
        candidate = next((p for p in valid_profiles if str(p["id"]) != str(admin_profile["id"])), None)
        if candidate is not None:
            driver_profile = _update_profile(
                session=session,
                supabase_url=supabase_url,
                service_key=service_key,
                profile_id=str(candidate["id"]),
                payload={"role": "driver", "empresa_id": empresa_id},
            )
        else:
            synthetic_email = f"driver-smoke-{uuid4().hex[:8]}@example.local"
            synthetic_id = _create_auth_user(
                session=session,
                supabase_url=supabase_url,
                service_key=service_key,
                email=synthetic_email,
            )
            existing = _select_profile_by_id(
                session=session,
                supabase_url=supabase_url,
                service_key=service_key,
                profile_id=synthetic_id,
            )
            if existing is not None:
                driver_profile = _update_profile(
                    session=session,
                    supabase_url=supabase_url,
                    service_key=service_key,
                    profile_id=synthetic_id,
                    payload={
                        "empresa_id": empresa_id,
                        "role": "driver",
                        "email": synthetic_email,
                        "username": f"driver_smoke_{synthetic_id[:8]}",
                    },
                )
            else:
                driver_profile = _insert_profile(
                    session=session,
                    supabase_url=supabase_url,
                    service_key=service_key,
                    payload={
                        "id": synthetic_id,
                        "empresa_id": empresa_id,
                        "role": "driver",
                        "email": synthetic_email,
                        "username": f"driver_smoke_{synthetic_id[:8]}",
                    },
                )

    return admin_profile, driver_profile


def _write_seed_file(admin_profile: dict[str, Any], driver_profile: dict[str, Any]) -> None:
    SEED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "admin_profile_id": str(admin_profile["id"]),
        "driver_profile_id": str(driver_profile["id"]),
        "admin_empresa_id": str(admin_profile.get("empresa_id") or ""),
        "driver_empresa_id": str(driver_profile.get("empresa_id") or ""),
    }
    SEED_OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    _load_env()
    supabase_url = _require_env("SUPABASE_URL")
    service_key = _require_env("SUPABASE_SERVICE_KEY")
    session = requests.Session()

    profiles = _select_profiles(session=session, supabase_url=supabase_url, service_key=service_key)
    if not profiles:
        raise RuntimeError("No profiles found. Seed baseline users first in Supabase Auth.")

    admin_profile, driver_profile = _ensure_admin_and_driver(
        session=session,
        supabase_url=supabase_url,
        service_key=service_key,
        profiles=profiles,
    )
    _write_seed_file(admin_profile=admin_profile, driver_profile=driver_profile)

    print("Seed completed successfully.")
    print(f"Admin profile id: {admin_profile['id']}")
    print(f"Driver profile id: {driver_profile['id']}")
    print(f"Seed file: {SEED_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
