"""
Aislamiento multi-tenant: un JWT de la empresa A no debe leer recursos de B (404/401).
"""

from __future__ import annotations

import pytest

from app.schemas.user import UserOut
from app.services.auth_service import AuthService

from tests.conftest import EMPRESA_A_ID


@pytest.mark.asyncio
async def test_porte_de_otro_tenant_devuelve_404(client, mock_user_empresa_a, monkeypatch) -> None:
    """
    Con identidad A, un ``porte_id`` que en BD pertenece a B no aparece en el filtro por ``empresa_id``
    (misma semántica que RLS: fila no visible → 404).
    """

    async def fake_profile(self: AuthService, *, subject: str) -> UserOut:
        return UserOut(
            username=str(subject),
            empresa_id=EMPRESA_A_ID,
            rol="user",
            usuario_id=None,
        )

    async def fake_ensure(self: AuthService, *, empresa_id: object) -> None:
        return None

    async def fake_rbac(self: AuthService, *, user: UserOut) -> None:
        return None

    monkeypatch.setattr(AuthService, "get_profile_by_subject", fake_profile)
    monkeypatch.setattr(AuthService, "ensure_empresa_context", fake_ensure)
    monkeypatch.setattr(AuthService, "ensure_rbac_context", fake_rbac)

    porte_empresa_b = "33333333-3333-3333-3333-333333333333"
    res = await client.get(
        f"/portes/{porte_empresa_b}",
        headers={"Authorization": f"Bearer {mock_user_empresa_a['jwt']}"},
    )
    assert res.status_code == 404
    assert res.json().get("detail") == "Porte no encontrado"
