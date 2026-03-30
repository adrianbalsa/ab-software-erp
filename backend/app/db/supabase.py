from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, cast

import anyio
from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings

_log = logging.getLogger(__name__)


class _SupabaseQuery(Protocol):
    def execute(self) -> Any: ...


class _SupabaseTable(Protocol):
    def select(self, columns: str = "*", **kwargs: Any) -> Any: ...
    def insert(self, data: Any) -> Any: ...
    def upsert(self, data: Any) -> Any: ...
    def update(self, data: Any) -> Any: ...
    def delete(self) -> Any: ...
    def eq(self, column: str, value: Any) -> Any: ...
    def in_(self, column: str, values: Any) -> Any: ...
    def gte(self, column: str, value: Any) -> Any: ...
    def gt(self, column: str, value: Any) -> Any: ...
    def lte(self, column: str, value: Any) -> Any: ...
    def lt(self, column: str, value: Any) -> Any: ...
    def is_(self, column: str, value: Any) -> Any: ...
    def order(self, column: str, desc: bool = False) -> Any: ...
    def limit(self, count: int) -> Any: ...
    def execute(self) -> Any: ...


class _SupabaseStorageBucket(Protocol):
    def upload(self, path: str, file: bytes, file_options: dict[str, Any] | None = None) -> Any: ...
    def create_signed_url(self, path: str, expires_in: int) -> Any: ...


class _SupabaseStorage(Protocol):
    def from_(self, bucket_name: str) -> _SupabaseStorageBucket: ...


class SupabaseAsync:
    """
    Async wrapper around supabase-py (which is synchronous).

    This keeps your FastAPI stack fully async by offloading I/O to a thread.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def table(self, name: str) -> _SupabaseTable:
        return cast(_SupabaseTable, self._client.table(name))

    @property
    def storage(self) -> _SupabaseStorage:
        return cast(_SupabaseStorage, self._client.storage)

    async def rpc(self, fn: str, params: dict[str, Any] | None = None) -> Any:
        def _call() -> Any:
            return self._client.rpc(fn, params or {}).execute()

        return await anyio.to_thread.run_sync(_call)

    async def execute(self, query: _SupabaseQuery) -> Any:
        return await anyio.to_thread.run_sync(query.execute)

    async def storage_upload(
        self,
        *,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str | None = None,
    ) -> Any:
        def _call() -> Any:
            opts = {"content-type": content_type} if content_type else None
            return self._client.storage.from_(bucket).upload(
                path=path,
                file=content,
                file_options=opts,
            )

        return await anyio.to_thread.run_sync(_call)

    async def storage_signed_url(self, *, bucket: str, path: str, expires_in: int) -> Any:
        def _call() -> Any:
            return self._client.storage.from_(bucket).create_signed_url(path, expires_in)

        return await anyio.to_thread.run_sync(_call)

    async def auth_admin_invite_user_by_email(
        self,
        *,
        email: str,
        options: dict[str, Any] | None = None,
    ) -> Any:
        def _call() -> Any:
            if options is None:
                return self._client.auth.admin.invite_user_by_email(email)
            return self._client.auth.admin.invite_user_by_email(email, options)

        return await anyio.to_thread.run_sync(_call)

    async def auth_admin_generate_link(
        self,
        *,
        email: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        def _call() -> Any:
            payload: dict[str, Any] = {
                "type": "invite",
                "email": email,
                "options": {"data": metadata or {}},
            }
            return self._client.auth.admin.generate_link(payload)

        return await anyio.to_thread.run_sync(_call)


def _extract_action_link(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        direct = raw.get("action_link") or raw.get("actionLink")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        data = raw.get("data")
        if isinstance(data, dict):
            nested = data.get("action_link") or data.get("actionLink")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    data_attr = getattr(raw, "data", None)
    if isinstance(data_attr, dict):
        nested_attr = data_attr.get("action_link") or data_attr.get("actionLink")
        if isinstance(nested_attr, str) and nested_attr.strip():
            return nested_attr.strip()
    for attr in ("action_link", "actionLink"):
        value = getattr(raw, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def auth_admin_generate_link(email: str, metadata: dict[str, Any]) -> str:
    """
    Genera magic link de invitación con cliente admin (service role).
    """
    db_admin = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    raw = await db_admin.auth_admin_generate_link(email=email, metadata=metadata)
    link = _extract_action_link(raw)
    if not link:
        raise RuntimeError("No se pudo generar action_link de onboarding")
    return link


@dataclass(frozen=True, slots=True)
class SupabaseDeps:
    client: SupabaseAsync


def _normalize_jwt_token(jwt_token: str | None) -> str | None:
    """Cadenas vacías o solo espacios → ``None`` (equivalente a no token)."""
    if jwt_token is None:
        return None
    t = str(jwt_token).strip()
    return t if t else None


def _create_sync_client(
    *,
    jwt_token: str | None,
    allow_service_role_bypass: bool,
    log_service_bypass_warning: bool,
) -> Client:
    """
    - Con JWT no vacío + clave **anon**: PostgREST aplica RLS con la identidad del token.
    - Sin JWT (``not token`` tras normalizar): **solo** clave **service role** si
      ``allow_service_role_bypass`` es True (llamadas internas explícitas, p. ej. health).
    - Sin JWT y sin bypass explícito: cliente **anon** sin cabecera ``Authorization`` (no bypass RLS).
    """
    settings = get_settings()
    url = settings.SUPABASE_URL
    anon_key = settings.SUPABASE_ANON_KEY
    service_key = settings.SUPABASE_SERVICE_KEY

    token = _normalize_jwt_token(jwt_token)
    if token:
        options = ClientOptions(headers={"Authorization": f"Bearer {token}"})
        return create_client(url, anon_key, options=options)

    # ``not token`` (tras normalizar) + bypass explícito → única ruta a service role.
    if allow_service_role_bypass:
        if log_service_bypass_warning:
            _log.warning("⚠️ Bypass RLS activo (cliente Supabase con service role)")
        return create_client(url, service_key)

    # Sin JWT y sin permiso explícito de service role: solo anon (RLS como rol anónimo).
    return create_client(url, anon_key)


async def get_supabase(
    *,
    jwt_token: str | None = None,
    allow_service_role_bypass: bool = False,
    log_service_bypass_warning: bool = True,
) -> SupabaseAsync:
    """
    Cliente **por petición**: no reutilizar un singleton entre usuarios (identidad RLS en cabecera).

    ``allow_service_role_bypass``: solo ``True`` en rutinas internas que deban usar
    ``SUPABASE_SERVICE_KEY`` (p. ej. ``/health``). Nunca por defecto.

    ``log_service_bypass_warning``: si ``False``, no se registra el aviso al usar service role
    (p. ej. health ruidoso).
    """
    client = await anyio.to_thread.run_sync(
        lambda: _create_sync_client(
            jwt_token=jwt_token,
            allow_service_role_bypass=allow_service_role_bypass,
            log_service_bypass_warning=log_service_bypass_warning,
        )
    )
    return SupabaseAsync(client)
