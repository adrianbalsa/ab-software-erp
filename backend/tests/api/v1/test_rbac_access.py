from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt

from app.api import deps
from app.api.v1.dependencies.auth import require_app_role
from app.core.config import get_settings
from app.models.enums import UserRole
from app.schemas.user import UserOut

_EMPRESA_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_PROFILE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class _StubAuthService:
    async def get_profile_by_subject(self, *, subject: str) -> UserOut | None:
        _ = subject
        return UserOut(
            username="rbac-test@ab-logistics.test",
            empresa_id=_EMPRESA_ID,
            role=UserRole.GESTOR,
            rol="user",
            rbac_role="traffic_manager",
            usuario_id=_PROFILE_ID,
        )

    async def ensure_empresa_context(self, *, empresa_id: UUID) -> None:
        _ = empresa_id

    async def ensure_rbac_context(self, *, user: UserOut) -> None:
        _ = user


def _build_supabase_style_jwt(*, app_role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(_PROFILE_ID),
        "role": "authenticated",
        "empresa_id": str(_EMPRESA_ID),
        "app_metadata": {"role": app_role},
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
async def rbac_test_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-app-jwt-secret-32-characters!")
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-role-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "unit-test-jwt-secret-at-least-32-chars")
    get_settings.cache_clear()

    app = FastAPI()

    @app.get("/finanzas/resumen")
    async def finanzas_resumen(_: UserOut = Depends(require_app_role("admin"))):
        return {"ok": True}

    @app.get("/me")
    async def me(current_user: UserOut = Depends(deps.get_current_user)):
        return {"rbac_role": current_user.rbac_role}

    app.dependency_overrides[deps.get_auth_service] = lambda: _StubAuthService()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_driver_gets_403_for_finance_endpoint(rbac_test_client: AsyncClient) -> None:
    token = _build_supabase_style_jwt(app_role="driver")
    res = await rbac_test_client.get("/finanzas/resumen", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_legacy_app_metadata_role_is_not_accepted(rbac_test_client: AsyncClient) -> None:
    token = _build_supabase_style_jwt(app_role="gestor")
    res = await rbac_test_client.get("/finanzas/resumen", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_finance_and_role_is_loaded(rbac_test_client: AsyncClient) -> None:
    token = _build_supabase_style_jwt(app_role="admin")
    finance_res = await rbac_test_client.get(
        "/finanzas/resumen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert finance_res.status_code == 200
    assert finance_res.json() == {"ok": True}

    me_res = await rbac_test_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["rbac_role"] == "admin"
