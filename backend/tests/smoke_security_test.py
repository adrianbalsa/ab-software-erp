from __future__ import annotations

import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from supabase import create_client

# Monorepo: ``.../backend/tests/`` → backend dir y raíz del repo.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import get_settings


def _load_env() -> None:
    load_dotenv(_ROOT / ".env", override=False)
    load_dotenv(_BACKEND_DIR / ".env", override=False)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jwt_sub_unverified(access_token: str) -> str:
    """Extract Auth user id from a Supabase access token (JWT `sub` claim)."""
    token = str(access_token or "").strip()
    parts = token.split(".")
    if len(parts) < 2:
        raise RuntimeError("Invalid JWT: missing payload segment")
    payload_b64 = parts[1]
    pad = (-len(payload_b64)) % 4
    if pad:
        payload_b64 += "=" * pad
    raw = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))
    sub = str(payload.get("sub") or "").strip()
    if not sub:
        raise RuntimeError("JWT payload missing sub (user id)")
    return sub


def _jwt_role_for_profile(role: str | None, legacy_rol: str | None) -> str:
    rr = (role or "").strip().lower()
    if rr:
        return rr
    legacy = (legacy_rol or "").strip().lower()
    if legacy:
        return legacy
    return "gestor"


@dataclass
class SmokeRunContext:
    base_url: str
    supabase_url: str
    service_key: str
    admin_profile: dict[str, Any]
    driver_profile: dict[str, Any]


class SmokeSecurityTest:
    def __init__(self) -> None:
        _load_env()
        settings = get_settings()
        self.base_url = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        self.supabase_url = settings.SUPABASE_URL.rstrip("/")
        self.service_key = settings.SUPABASE_SERVICE_KEY
        self.session = requests.Session()
        self.session.timeout = 20
        self._ctx: SmokeRunContext | None = None
        self._admin_token: str | None = None
        self._driver_token: str | None = None
        self.failure_reasons: dict[str, str] = {}
        self.supabase_auth = create_client(self.supabase_url, settings.SUPABASE_KEY)

    def _set_failure_reason(self, case_name: str, reason: str) -> None:
        self.failure_reasons[case_name] = reason

    def _clear_failure_reason(self, case_name: str) -> None:
        self.failure_reasons.pop(case_name, None)

    def _wait_for_api_live(self, timeout_seconds: int = 90) -> None:
        deadline = time.time() + timeout_seconds
        health_urls = [f"{self.base_url}/health", f"{self.base_url}/api/v1/health"]
        last_error = "health check not started"
        while time.time() < deadline:
            for url in health_urls:
                try:
                    res = self.session.get(url, timeout=5)
                    if res.status_code == 200:
                        payload = res.json() if "application/json" in (res.headers.get("Content-Type") or "") else {}
                        status_text = str(payload.get("status") or "").strip().lower()
                        if status_text in {"healthy", "live", "ok"} or not status_text:
                            return
                        last_error = f"{url} status={status_text or 'unknown'}"
                    else:
                        last_error = f"{url} http={res.status_code}"
                except Exception as exc:
                    last_error = f"{url} error={exc!s}"
            time.sleep(2)
        raise RuntimeError(f"API is not Live after {timeout_seconds}s: {last_error}")

    def _sb_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    def _supabase_select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        url = f"{self.supabase_url}/rest/v1/{table}"
        res = self.session.get(url, headers=self._sb_headers(), params=params, timeout=20)
        if res.status_code >= 400:
            raise RuntimeError(f"Supabase {table} query failed ({res.status_code}): {res.text}")
        data = res.json()
        if isinstance(data, list):
            return data
        return []

    def _supabase_insert(self, table: str, payload: dict[str, Any], select: str = "*") -> dict[str, Any]:
        url = f"{self.supabase_url}/rest/v1/{table}"
        res = self.session.post(
            url,
            headers=self._sb_headers(),
            params={"select": select},
            json=payload,
            timeout=20,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"Supabase {table} insert failed ({res.status_code}): {res.text}")
        rows = res.json()
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(f"Supabase {table} insert returned no rows")
        return rows[0]

    def _supabase_delete_by_id(self, table: str, row_id: int) -> None:
        url = f"{self.supabase_url}/rest/v1/{table}"
        res = self.session.delete(
            url,
            headers=self._sb_headers(),
            params={"id": f"eq.{row_id}"},
            timeout=20,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"Supabase {table} delete failed ({res.status_code}): {res.text}")

    def _profile_password(self, profile: dict[str, Any], *, kind: str) -> str:
        explicit = os.getenv(f"SMOKE_{kind.upper()}_PASSWORD", "").strip()
        if explicit:
            return explicit
        default_pwd = os.getenv("SMOKE_TEST_PASSWORD", "").strip()
        if default_pwd:
            return default_pwd
        email = str(profile.get("email") or "").strip()
        raise RuntimeError(
            f"Missing password for {kind} test login ({email}). "
            f"Set SMOKE_{kind.upper()}_PASSWORD or SMOKE_TEST_PASSWORD."
        )

    def _get_access_token_for_profile(self, profile: dict[str, Any], *, kind: str) -> str:
        email = str(profile.get("email") or "").strip()
        if not email:
            raise RuntimeError(f"{kind} profile has no email for Supabase login")
        password = self._profile_password(profile, kind=kind)
        auth_response = self.supabase_auth.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session = getattr(auth_response, "session", None)
        access_token = str(getattr(session, "access_token", "") or "").strip()
        if not access_token:
            raise RuntimeError(f"Supabase auth did not return access_token for {kind} ({email})")
        return access_token

    def _smoke_login_emails(self) -> tuple[str, str]:
        admin_email = os.getenv("SMOKE_ADMIN_EMAIL", "debug-smoke@example.local").strip()
        driver_email = os.getenv("SMOKE_DRIVER_EMAIL", "driver-smoke-f15a6a94@example.local").strip()
        if not admin_email or not driver_email:
            raise RuntimeError("SMOKE_ADMIN_EMAIL and SMOKE_DRIVER_EMAIL must be set and non-empty")
        return admin_email, driver_email

    def _fetch_profile_by_user_id(self, user_id: str) -> dict[str, Any]:
        rows = self._supabase_select(
            "profiles",
            {
                "select": "id,username,email,empresa_id,role",
                "id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if not rows:
            raise RuntimeError(
                f"No profile row for auth user id={user_id}. "
                "Ensure Supabase Auth and public.profiles are aligned (e.g. backend/fix_auth.py)."
            )
        return rows[0]

    def _get_tokens(self, ctx: SmokeRunContext) -> tuple[str, str]:
        if self._admin_token and self._driver_token:
            return self._admin_token, self._driver_token
        admin_token = self._get_access_token_for_profile(ctx.admin_profile, kind="admin")
        driver_token = self._get_access_token_for_profile(ctx.driver_profile, kind="driver")
        self._admin_token = admin_token
        self._driver_token = driver_token
        return admin_token, driver_token

    def _setup(self) -> SmokeRunContext:
        if self._ctx is not None:
            return self._ctx
        admin_email, driver_email = self._smoke_login_emails()

        admin_token = self._get_access_token_for_profile({"email": admin_email}, kind="admin")
        driver_token = self._get_access_token_for_profile({"email": driver_email}, kind="driver")
        self._admin_token = admin_token
        self._driver_token = driver_token

        admin_id = _jwt_sub_unverified(admin_token)
        driver_id = _jwt_sub_unverified(driver_token)

        admin_profile = self._fetch_profile_by_user_id(admin_id)
        driver_profile = self._fetch_profile_by_user_id(driver_id)

        if str(admin_profile.get("email") or "").strip().lower() != admin_email.lower():
            raise RuntimeError(
                f"Admin JWT sub profile email mismatch: expected {admin_email!r}, "
                f"got {admin_profile.get('email')!r}"
            )
        if str(driver_profile.get("email") or "").strip().lower() != driver_email.lower():
            raise RuntimeError(
                f"Driver JWT sub profile email mismatch: expected {driver_email!r}, "
                f"got {driver_profile.get('email')!r}"
            )

        self._ctx = SmokeRunContext(
            base_url=self.base_url,
            supabase_url=self.supabase_url,
            service_key=self.service_key,
            admin_profile=admin_profile,
            driver_profile=driver_profile,
        )
        return self._ctx

    def _api_get(self, path: str, token: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        print(f"Testing URL: {url}")
        return self.session.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )

    def _api_post(self, path: str, token: str, payload: dict[str, Any] | None = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        print(f"Testing URL: {url}")
        return self.session.post(
            url,
            json=payload or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )

    def case_1_rbac_negative(self, driver_token: str) -> bool:
        case_name = "Test Case 1"
        res = self._api_get("/api/v1/finance/treasury-risk", driver_token)
        ok = res.status_code == 403
        if ok:
            self._clear_failure_reason(case_name)
        else:
            self._set_failure_reason(
                case_name,
                f"Code: {res.status_code}, Body: {res.text}",
            )
        return ok

    def case_2_rbac_positive(self, admin_token: str) -> tuple[bool, str]:
        case_name = "Test Case 2"
        ts = _iso_now()
        res = self._api_get("/api/v1/finance/treasury-risk", admin_token)
        ok = res.status_code == 200
        if ok:
            self._clear_failure_reason(case_name)
        else:
            self._set_failure_reason(
                case_name,
                f"Code: {res.status_code}, Body: {res.text}",
            )
        return (ok, ts)

    def case_3_rls_tenant_isolation(self, admin_token: str, admin_empresa_id: str) -> bool:
        case_name = "Test Case 3"
        facturas = self._supabase_select(
            "facturas",
            {
                "select": "id,empresa_id",
                "order": "id.desc",
                "limit": "500",
            },
        )
        foreign = next((f for f in facturas if str(f.get("empresa_id")) != admin_empresa_id), None)
        if foreign is None:
            self._set_failure_reason(case_name, "No foreign factura found to validate tenant isolation")
            return False
        factura_id = int(foreign["id"])
        res = self._api_get(f"/api/v1/facturas/{factura_id}", admin_token)
        ok = res.status_code in {403, 404}
        if ok:
            self._clear_failure_reason(case_name)
        else:
            self._set_failure_reason(
                case_name,
                f"Code: {res.status_code}, Body: {res.text}",
            )
        return ok

    def case_4_audit_trail(self, admin_profile: dict[str, Any], since_iso: str) -> bool:
        case_name = "Test Case 4"
        user_id = str(admin_profile.get("id") or "").strip()
        if not user_id:
            self._set_failure_reason(case_name, "Admin profile missing user id")
            return False
        rows = self._supabase_select(
            "audit_logs",
            {
                "select": "id,action,changed_by,table_name,record_id,created_at,new_data",
                "changed_by": f"eq.{user_id}",
                "created_at": f"gte.{since_iso}",
                "order": "created_at.desc",
                "limit": "100",
            },
        )
        ok = len(rows) > 0
        if ok:
            self._clear_failure_reason(case_name)
        else:
            self._set_failure_reason(case_name, "No audit trail rows found for admin user in expected time window")
        return ok

    def case_5_worker_audit_mock(self, driver_token: str) -> bool:
        """RBAC on an admin-only finance route (no AEAT / invoice side effects)."""
        case_name = "Test Case 5"
        res = self._api_get("/api/v1/finance/treasury-risk", driver_token)
        ok = res.status_code == 403
        if ok:
            self._clear_failure_reason(case_name)
        else:
            self._set_failure_reason(
                case_name,
                f"Case 5 RBAC: expected status 403, got {res.status_code}, Body: {res.text}",
            )
        return ok

    def run(self) -> dict[str, bool]:
        self._wait_for_api_live()
        ctx = self._setup()
        admin_token, driver_token = self._get_tokens(ctx)
        admin_empresa_id = str(ctx.admin_profile["empresa_id"])

        try:
            c1 = self.case_1_rbac_negative(driver_token)
        except Exception as e:
            c1 = False
            self._set_failure_reason("Test Case 1", str(e))
        try:
            c2, case2_ts = self.case_2_rbac_positive(admin_token)
        except Exception as e:
            c2 = False
            case2_ts = _iso_now()
            self._set_failure_reason("Test Case 2", str(e))
        try:
            c3 = self.case_3_rls_tenant_isolation(admin_token, admin_empresa_id)
        except Exception as e:
            c3 = False
            self._set_failure_reason("Test Case 3", str(e))
        try:
            c4 = self.case_4_audit_trail(ctx.admin_profile, case2_ts) if c2 else False
            if not c2 and not self.failure_reasons.get("Test Case 4"):
                self._set_failure_reason("Test Case 4", "Skipped because Test Case 2 failed")
        except Exception as e:
            c4 = False
            self._set_failure_reason("Test Case 4", str(e))
        try:
            c5 = self.case_5_worker_audit_mock(driver_token)
        except Exception as e:
            c5 = False
            self._set_failure_reason("Test Case 5", str(e))

        return {
            "Test Case 1": c1,
            "Test Case 2": c2,
            "Test Case 3": c3,
            "Test Case 4": c4,
            "Test Case 5": c5,
        }


def main() -> int:
    tester = SmokeSecurityTest()
    try:
        results = tester.run()
    except Exception as e:
        results = {
            "Test Case 1": False,
            "Test Case 2": False,
            "Test Case 3": False,
            "Test Case 4": False,
            "Test Case 5": False,
        }
        tester._set_failure_reason("Test Case 1", str(e))
        tester._set_failure_reason("Test Case 2", str(e))
        tester._set_failure_reason("Test Case 3", str(e))
        tester._set_failure_reason("Test Case 4", str(e))
        tester._set_failure_reason("Test Case 5", str(e))
    for name, ok in results.items():
        if ok:
            print(f"{name}: Pass")
        else:
            reason = tester.failure_reasons.get(name, "Unknown reason")
            print(f"{name}: Fail - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
