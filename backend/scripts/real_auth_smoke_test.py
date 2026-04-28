"""Login with a real owner identity and trigger admin alert smoke test."""

from __future__ import annotations

import os
from pprint import pformat

import httpx


def _safe_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except Exception:
        return response.text


def main() -> int:
    base_url = os.getenv("SMOKE_TEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    username = os.getenv("SMOKE_OWNER_USERNAME", "test_owner@ablogistics.com").strip()
    password = os.getenv("SMOKE_OWNER_PASSWORD", "password123").strip()
    host_header = os.getenv("SMOKE_TEST_HOST_HEADER", "").strip()

    if not username or not password:
        print("ERROR: define SMOKE_OWNER_USERNAME y SMOKE_OWNER_PASSWORD")
        return 1

    login_candidates = (
        f"{base_url}/api/v1/auth/login",
        f"{base_url}/auth/login",
    )
    alert_url = f"{base_url}/api/v1/admin/test-alert"

    with httpx.Client(timeout=20.0) as client:
        login_resp = None
        for login_url in login_candidates:
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if host_header:
                headers["Host"] = host_header
            login_resp = client.post(
                login_url,
                data={"username": username, "password": password},
                headers=headers,
            )
            print(f"=== LOGIN TRY {login_url} ===")
            print(f"status={login_resp.status_code}")
            print(pformat(_safe_json(login_resp)))
            if login_resp.status_code == 200:
                break

        assert login_resp is not None
        print("=== LOGIN RESPONSE ===")
        print(f"status={login_resp.status_code}")
        print(pformat(_safe_json(login_resp)))

        if login_resp.status_code != 200:
            print("ERROR: login failed, smoke-test no ejecutado.")
            return 1

        token = str((_safe_json(login_resp) or {}).get("access_token") or "").strip()
        if not token:
            print("ERROR: login no devolvió access_token.")
            return 1

        alert_headers = {"Authorization": f"Bearer {token}"}
        if host_header:
            alert_headers["Host"] = host_header
        alert_resp = client.post(alert_url, headers=alert_headers)
        print("=== ALERT RESPONSE ===")
        print(f"status={alert_resp.status_code}")
        print(pformat(_safe_json(alert_resp)))

        if alert_resp.status_code in (200, 202):
            print("SUCCESS: endpoint accepted request (200/202).")
            return 0

        print("ERROR: endpoint did not return 200/202.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
