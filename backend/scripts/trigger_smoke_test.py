"""Trigger local smoke-test endpoint for Discord alert integration."""

from __future__ import annotations

import os

import httpx


def main() -> int:
    base_url = os.getenv("SMOKE_TEST_BASE_URL", "http://127.0.0.1:8000")
    token = os.getenv("SMOKE_TEST_BEARER_TOKEN", "").strip()
    url = f"{base_url.rstrip('/')}/api/v1/admin/test-alert"

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.post(url, headers=headers, timeout=20.0)
    except Exception as exc:  # pragma: no cover - utility script
        print(f"ERROR: request failed -> {exc}")
        return 1

    print(f"POST {url}")
    print(f"status={response.status_code}")
    if response.text.strip():
        print(f"body={response.text.strip()}")

    if response.status_code in (200, 202):
        print("OK: smoke-test endpoint accepted request.")
        return 0

    if response.status_code in (401, 403) and not token:
        print("TIP: export SMOKE_TEST_BEARER_TOKEN='<jwt_admin>' and retry.")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
