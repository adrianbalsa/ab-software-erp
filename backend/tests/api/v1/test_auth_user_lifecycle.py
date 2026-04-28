from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID

from app.api.v1 import auth as auth_v1
from app.core.config import get_settings
from app.models.enums import UserRole
from app.schemas.user import UserOut


def _test_headers() -> dict[str, str]:
    allowed = get_settings().ALLOWED_HOSTS
    host = next((h for h in allowed if h and h != "*"), "testserver")
    return {"Host": host}


@dataclass
class _FakeAuthDb:
    invite_user_id: str | None = "11111111-1111-1111-1111-111111111111"
    invite_calls: list[dict[str, object]] = field(default_factory=list)
    upsert_payloads: list[dict[str, object]] = field(default_factory=list)
    reset_calls: list[dict[str, object]] = field(default_factory=list)
    verify_payloads: list[dict[str, object]] = field(default_factory=list)
    update_payloads: list[dict[str, object]] = field(default_factory=list)

    async def auth_admin_invite_user_by_email(self, *, email: str, options: dict[str, object]) -> object:
        self.invite_calls.append({"email": email, "options": options})
        if self.invite_user_id is None:
            return {}
        return {"user": {"id": self.invite_user_id}}

    def table(self, name: str) -> "_FakeAuthDb":
        assert name == "profiles"
        return self

    def upsert(self, payload: dict[str, object]) -> "_FakeAuthDb":
        self.upsert_payloads.append(payload)
        return self

    async def execute(self, _query: object) -> object:
        return SimpleNamespace(data=[{}])

    async def auth_reset_password_for_email(
        self,
        *,
        email: str,
        options: dict[str, object] | None = None,
    ) -> object:
        self.reset_calls.append({"email": email, "options": options})
        return {"ok": True}

    async def auth_verify_otp(self, payload: dict[str, object]) -> object:
        self.verify_payloads.append(payload)
        return {"ok": True}

    async def auth_update_user(self, attributes: dict[str, object]) -> object:
        self.update_payloads.append(attributes)
        return {"ok": True}


class _RefreshServiceStub:
    def __init__(self) -> None:
        self.resolve_called = False
        self.revoke_called = False

    async def resolve_current_session_id(self, *, raw_refresh: str | None) -> str | None:
        self.resolve_called = True
        if raw_refresh:
            return "sess-123"
        return None

    async def revoke_session_for_user(self, *, session_id: str, user_id: str) -> bool:
        self.revoke_called = True
        return bool(session_id and user_id)


def _owner_user() -> UserOut:
    return UserOut(
        username="owner@ablogistics.test",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role=UserRole.ADMIN,
        rol="admin",
        rbac_role="owner",
        usuario_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
    )


async def test_invite_user_staff_propagates_empresa_id(client) -> None:
    fake_db = _FakeAuthDb()
    app = client._transport.app
    app.dependency_overrides[auth_v1.get_db_admin] = lambda: fake_db
    try:
        res = await client.post(
            "/api/v1/auth/invite",
                json={"email": "staff@example.com", "role": "staff"},
            headers=_test_headers(),
        )
    finally:
        app.dependency_overrides.pop(auth_v1.get_db_admin, None)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["invited_email"] == "staff@example.com"
    assert body["role"] == "staff"
    assert fake_db.invite_calls, "Debe invocar supabase.auth.admin.invite_user_by_email"
    assert fake_db.upsert_payloads, "Debe asegurar empresa_id en profiles"
    profile_payload = fake_db.upsert_payloads[0]
    assert profile_payload["empresa_id"] == body["empresa_id"]
    assert profile_payload["role"] == "traffic_manager"


async def test_send_reset_password_uses_supabase_recovery(client) -> None:
    fake_db = _FakeAuthDb()
    app = client._transport.app
    app.dependency_overrides[auth_v1.get_db_anon] = lambda: fake_db
    try:
        res = await client.post(
            "/api/v1/auth/reset-password",
                json={"email": "staff@example.com"},
            headers=_test_headers(),
        )
    finally:
        app.dependency_overrides.pop(auth_v1.get_db_anon, None)

    assert res.status_code == 200, res.text
    assert fake_db.reset_calls
    assert fake_db.reset_calls[0]["email"] == "staff@example.com"


async def test_confirm_reset_password_verifies_token_and_updates_password(client) -> None:
    fake_db = _FakeAuthDb()
    app = client._transport.app
    app.dependency_overrides[auth_v1.get_db_anon] = lambda: fake_db
    try:
        res = await client.post(
            "/api/v1/auth/reset-password/confirm",
            json={"token": "123456", "new_password": "NuevaClave!2026"},
            headers=_test_headers(),
        )
    finally:
        app.dependency_overrides.pop(auth_v1.get_db_anon, None)

    assert res.status_code == 200, res.text
    assert fake_db.verify_payloads == [{"type": "recovery", "token": "123456"}]
    assert fake_db.update_payloads == [{"password": "NuevaClave!2026"}]


async def test_logout_revokes_current_session_when_cookie_present(client) -> None:
    refresh_stub = _RefreshServiceStub()
    app = client._transport.app
    app.dependency_overrides[auth_v1.deps.get_refresh_token_service] = lambda: refresh_stub
    app.dependency_overrides[auth_v1.deps.get_usuario_db_id] = lambda: "dddddddd-dddd-dddd-dddd-dddddddddddd"
    app.dependency_overrides[auth_v1.deps.get_current_user] = _owner_user
    client.cookies.set("abl_refresh", "raw-refresh-cookie")
    try:
        res = await client.post(
            "/api/v1/auth/logout",
            headers=_test_headers(),
        )
    finally:
        app.dependency_overrides.pop(auth_v1.deps.get_refresh_token_service, None)
        app.dependency_overrides.pop(auth_v1.deps.get_usuario_db_id, None)
        app.dependency_overrides.pop(auth_v1.deps.get_current_user, None)

    assert res.status_code == 200, res.text
    assert refresh_stub.resolve_called is True
    assert refresh_stub.revoke_called is True
