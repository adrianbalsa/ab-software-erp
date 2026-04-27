"""
Seguridad auth: migración lazy SHA-256 → Argon2id y rotación de refresh tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.core.security import hash_password_argon2id, hash_refresh_token, sha256_hex
from app.schemas.user import UserInDB, UserOut
from app.services.auth_service import AuthService, PasswordResetRequired
from app.services.refresh_token_service import RefreshTokenService

from tests.conftest import EMPRESA_A_ID


def _data(rows: list[object]) -> SimpleNamespace:
    return SimpleNamespace(data=rows)


@pytest.mark.asyncio
async def test_lazy_migration_sha256_to_argon2id_tras_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tras login válido, ``password_hash`` legacy (hex SHA-256) se reescribe con Argon2id."""
    password = "ClaveSegura!2026"
    legacy_hex = sha256_hex(password)

    user_row = UserInDB(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        username="legacy_user@test",
        empresa_id=EMPRESA_A_ID,
        rol="user",
        password_hash=legacy_hex,
    )

    argon2_calls: list[bool] = []

    def spy_hash_password(pwd: str) -> str:
        argon2_calls.append(True)
        return hash_password_argon2id(pwd)

    monkeypatch.setattr("app.services.auth_service.hash_password_argon2id", spy_hash_password)

    async def fake_get_user(self: AuthService, *, username: str) -> UserInDB | None:
        if username == user_row.username:
            return user_row
        return None

    async def fake_profile(self: AuthService, *, subject: str) -> UserOut:
        return UserOut(
            username=user_row.username,
            empresa_id=EMPRESA_A_ID,
            rol="user",
            usuario_id=user_row.id,
        )

    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())
    db.execute = AsyncMock(return_value=_data([{}]))

    svc = AuthService(db)

    with (
        patch.object(AuthService, "get_user", fake_get_user),
        patch.object(AuthService, "get_profile_by_subject", fake_profile),
    ):
        out = await svc.authenticate(username=user_row.username, password=password)

    assert out is not None
    assert argon2_calls == [True], "Migración lazy debe invocar Argon2id tras validar SHA-256"


@pytest.mark.asyncio
async def test_password_must_reset_bloquea_login_sha256_legacy() -> None:
    """Con credenciales válidas, una cuenta marcada no recibe sesión ni migración lazy."""
    password = "ClaveSegura!2026"
    user_row = UserInDB(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        username="legacy_reset@test",
        empresa_id=EMPRESA_A_ID,
        rol="user",
        password_hash=sha256_hex(password),
        password_must_reset=True,
    )

    async def fake_get_user(self: AuthService, *, username: str) -> UserInDB | None:
        if username == user_row.username:
            return user_row
        return None

    db = MagicMock()
    db.execute = AsyncMock()
    svc = AuthService(db)

    with patch.object(AuthService, "get_user", fake_get_user):
        with pytest.raises(PasswordResetRequired) as exc:
            await svc.authenticate(username=user_row.username, password=password)

    assert exc.value.username == user_row.username
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_password_for_username_limpia_password_must_reset() -> None:
    user_row = UserInDB(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        username="reset@test",
        empresa_id=EMPRESA_A_ID,
        rol="user",
        password_hash=sha256_hex("old-password"),
        password_must_reset=True,
    )

    async def fake_get_user(self: AuthService, *, username: str) -> UserInDB | None:
        if username == user_row.username:
            return user_row
        return None

    table = MagicMock()
    table.update.return_value = table
    table.eq.return_value = table
    db = MagicMock()
    db.table.return_value = table
    db.execute = AsyncMock(return_value=_data([{}]))
    svc = AuthService(db)

    with patch.object(AuthService, "get_user", fake_get_user):
        ok = await svc.set_password_for_username(
            username=user_row.username,
            new_plain_password="NuevaClave!2026",
        )

    assert ok is True
    update_payload = table.update.call_args.args[0]
    assert update_payload["password_must_reset"] is False
    assert update_payload["password_hash"].startswith("$argon2id$")


class _UsuariosQuery:
    def __init__(self, db: "_LegacyMarkerDb", op: str = "select") -> None:
        self.db = db
        self.op = op
        self.payload: dict[str, object] = {}
        self.filters: list[tuple[str, object]] = []

    def select(self, _columns: str) -> "_UsuariosQuery":
        self.op = "select"
        return self

    def limit(self, count: int) -> "_UsuariosQuery":
        self.payload["limit"] = count
        return self

    def update(self, payload: dict[str, object]) -> "_UsuariosQuery":
        self.op = "update"
        self.payload.update(payload)
        return self

    def eq(self, column: str, value: object) -> "_UsuariosQuery":
        self.filters.append((column, value))
        return self


class _LegacyMarkerDb:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.updates: list[_UsuariosQuery] = []

    def table(self, name: str) -> _UsuariosQuery:
        assert name == "usuarios"
        return _UsuariosQuery(self)

    async def execute(self, query: _UsuariosQuery) -> SimpleNamespace:
        if query.op == "select":
            return _data(self.rows)
        self.updates.append(query)
        return _data([{}])


@pytest.mark.asyncio
async def test_mark_legacy_sha256_passwords_for_reset_solo_marca_sha256_no_marcados() -> None:
    db = _LegacyMarkerDb(
        [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "username": "legacy@test",
                "password_hash": sha256_hex("ClaveSegura!2026"),
                "password_must_reset": False,
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "username": "argon@test",
                "password_hash": hash_password_argon2id("ClaveSegura!2026"),
                "password_must_reset": False,
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "username": "already@test",
                "password_hash": sha256_hex("ClaveSegura!2026"),
                "password_must_reset": True,
            },
        ]
    )

    marked = await AuthService(db).mark_legacy_sha256_passwords_for_reset(limit=50)  # type: ignore[arg-type]

    assert marked == 1
    assert db.updates[0].payload == {"password_must_reset": True}
    assert db.updates[0].filters == [("id", "11111111-1111-1111-1111-111111111111")]


@pytest.mark.asyncio
async def test_refresh_token_issue_produces_distinct_opaques() -> None:
    """Cada emisión de refresh usa un opaco nuevo (base de la rotación en /auth/refresh)."""
    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())
    db.execute = AsyncMock(return_value=_data([{}]))
    svc = RefreshTokenService(db)

    with patch(
        "app.services.refresh_token_service.secrets.token_urlsafe",
        side_effect=["primer-opaco-muy-largo-token-urlsafe-48chars-xx", "segundo-opaco-distinto-token-urlsafe-48chars-yy"],
    ):
        t1, _ = await svc.issue_new_refresh(user_id="u1")
        t2, _ = await svc.issue_new_refresh(user_id="u1")

    assert t1 != t2
    assert hash_refresh_token(t1) != hash_refresh_token(t2)


@pytest.mark.asyncio
async def test_rotate_revokes_y_emite_nuevo_refresh_distinto() -> None:
    """``rotate`` invalida el hash actual y devuelve un nuevo refresh distinto del usado."""
    user_id = "55555555-5555-5555-5555-555555555555"
    raw_refresh = "cookie-opaco-inicial-refresh-token"
    th = hash_refresh_token(raw_refresh)
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    row_rt = {
        "id": "sess-orig",
        "user_id": user_id,
        "token_hash": th,
        "revoked": False,
        "expires_at": future,
    }
    user_row = {
        "id": user_id,
        "username": "rot@test",
        "empresa_id": str(EMPRESA_A_ID),
        "rol": "user",
        "password_hash": "x",
    }

    exec_responses = [
        _data([row_rt]),
        _data([{**row_rt, "revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}]),
        _data([user_row]),
        _data([{}]),
    ]

    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())
    db.execute = AsyncMock(side_effect=exec_responses)

    svc = RefreshTokenService(db)
    auth = AuthService(db)

    async def fake_profile(self: AuthService, *, subject: str) -> UserOut:
        return UserOut(
            username="rot@test",
            empresa_id=EMPRESA_A_ID,
            rol="user",
            usuario_id=UUID(user_id),
        )

    with patch.object(AuthService, "get_profile_by_subject", fake_profile):
        with patch(
            "app.services.refresh_token_service.secrets.token_urlsafe",
            return_value="nuevo-opaco-tras-rotacion-urlsafe-token-48chars-zz",
        ):
            access, new_raw, _max_age, user_out = await svc.rotate(
                raw_refresh=raw_refresh,
                auth_service=auth,
            )

    assert access
    assert new_raw != raw_refresh
    assert user_out.empresa_id == EMPRESA_A_ID
