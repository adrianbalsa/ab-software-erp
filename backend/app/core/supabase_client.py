from __future__ import annotations

from supabase.client import AsyncClient, create_async_client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings

_base_opts = ClientOptions(
    postgrest_client_timeout=10,
    storage_client_timeout=10,
)


def _auth_opts(access_token: str | None = None) -> ClientOptions:
    token = str(access_token or "").strip()
    if not token:
        return _base_opts
    return ClientOptions(
        postgrest_client_timeout=10,
        storage_client_timeout=10,
        headers={"Authorization": f"Bearer {token}"},
    )


async def get_supabase_async_client(access_token: str | None = None) -> AsyncClient:
    """
    Devuelve un cliente AsyncClient por request con cabecera Authorization para RLS.
    """
    return await create_async_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_KEY,
        options=_auth_opts(access_token),
    )