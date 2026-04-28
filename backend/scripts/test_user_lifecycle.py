"""Smoke test IAM lifecycle: owner invite + staff login."""

from __future__ import annotations

import os
from pprint import pformat

import httpx


def _safe_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except Exception:
        return response.text


def _login(client: httpx.Client, base_url: str, username: str, password: str) -> tuple[int, dict]:
    login_candidates = (
        f"{base_url}/api/v1/auth/login",
        f"{base_url}/auth/login",
    )
    payload: dict = {}
    last_status = 0
    for url in login_candidates:
        resp = client.post(
            url,
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        body = _safe_json(resp)
        print(f"LOGIN {url} -> {resp.status_code}")
        print(pformat(body))
        last_status = resp.status_code
        if resp.status_code == 200 and isinstance(body, dict):
            payload = body
            break
    return last_status, payload


def main() -> int:
    base_url = os.getenv("SMOKE_TEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    owner_username = os.getenv("SMOKE_OWNER_USERNAME", "test_owner@ablogistics.com").strip()
    owner_password = os.getenv("SMOKE_OWNER_PASSWORD", "password123").strip()
    staff_email = os.getenv("SMOKE_STAFF_EMAIL", "test_staff@ablogistics.com").strip().lower()
    staff_password = os.getenv("SMOKE_STAFF_PASSWORD", "").strip()

    with httpx.Client(timeout=25.0) as client:
        owner_status, owner_body = _login(client, base_url, owner_username, owner_password)
        if owner_status != 200:
            print("ERROR: owner login failed.")
            return 1

        owner_token = str(owner_body.get("access_token") or "").strip()
        if not owner_token:
            print("ERROR: owner login returned no access_token.")
            return 1

        invite_url = f"{base_url}/api/v1/auth/invite"
        invite_resp = client.post(
            invite_url,
            json={"email": staff_email, "role": "staff"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        invite_body = _safe_json(invite_resp)
        print(f"INVITE {invite_url} -> {invite_resp.status_code}")
        print(pformat(invite_body))

        if invite_resp.status_code not in (200, 201):
            print("ERROR: invite endpoint failed.")
            return 1

        if not staff_password:
            print("WARN: SMOKE_STAFF_PASSWORD no definido; invitación validada, login staff omitido.")
            return 0

        staff_status, _ = _login(client, base_url, staff_email, staff_password)
        if staff_status != 200:
            print("ERROR: staff login failed after invitation.")
            return 1

        print("SUCCESS: invitation and staff login completed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
