"""
Interfaz única de lectura de secretos (Due Diligence #115).

- **env** / **railway** (por defecto): variables de entorno.
- **vault**: KV v2 en HashiCorp Vault. Auth: ``token`` (default), ``kubernetes`` o ``approle``.
  Sin configuración suficiente: ``SaaSEnvSecretProvider`` (secretos por entorno).
- **aws** / **secretsmanager**: un secreto en **AWS Secrets Manager** (JSON con las mismas
  claves que el inventario). Sin ``AWS_SECRETS_MANAGER_SECRET_ID``: vuelve a **env**.

``bump_integration_secret_version()`` invalida cachés en proceso (integraciones + payload JSON).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import hvac
from hvac.exceptions import Forbidden

_log = logging.getLogger(__name__)

_vault_backend_warned = False
_aws_backend_warned = False

_integration_secret_version: int = 0


def bump_integration_secret_version() -> int:
    """Incrementa la versión de credenciales; fuerza reconstrucción de clientes integrados."""
    global _integration_secret_version
    _integration_secret_version += 1
    return _integration_secret_version


def get_integration_secret_version() -> int:
    return _integration_secret_version


def reset_secret_manager() -> None:
    """Limpia singleton (tests / reload)."""
    get_secret_manager.cache_clear()


class SecretManagerService(ABC):
    """Contrato alineado con backends Vault / AWS Secrets Manager."""

    @abstractmethod
    def get_stripe_secret_key(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_stripe_webhook_secret(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_gocardless_access_token(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_gocardless_secret_id(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_gocardless_secret_key(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_gocardless_webhook_secret(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_jwt_secret_key(self) -> str:
        """Secreto HS256 de la API (login propio); obligatorio en runtime válido."""

    @abstractmethod
    def get_gocardless_env(self) -> str:
        ...

    @abstractmethod
    def list_fernet_pii_raw_keys(self, *, include_previous: bool) -> tuple[str, ...]:
        ...

    @abstractmethod
    def list_fernet_storage_raw_keys(self, *, include_previous: bool) -> tuple[str, ...]:
        ...

    @abstractmethod
    def get_openai_api_key(self) -> Optional[str]:
        """Clave API OpenAI (completions / SDK). Opcional si no se usa ese proveedor."""

    @abstractmethod
    def get_anthropic_api_key(self) -> Optional[str]:
        """Clave Anthropic / Claude (``ANTHROPIC_API_KEY`` o alias ``CLAUDE_API_KEY``)."""

    @abstractmethod
    def get_google_gemini_api_key(self) -> Optional[str]:
        """Google AI / Gemini (``GEMINI_API_KEY`` o ``GOOGLE_API_KEY``)."""

    @abstractmethod
    def get_azure_openai_api_key(self) -> Optional[str]:
        """Azure OpenAI (``AZURE_API_KEY`` o ``AZURE_OPENAI_API_KEY``)."""

    @abstractmethod
    def get_azure_document_intelligence_endpoint(self) -> Optional[str]:
        """Endpoint Azure Document Intelligence (OCR facturas), p. ej. ``AZURE_ENDPOINT``."""

    @abstractmethod
    def get_azure_document_intelligence_key(self) -> Optional[str]:
        """Clave Azure Document Intelligence (``AZURE_KEY``)."""


def _strip(name: str) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _read_first_non_empty_line(path: str) -> Optional[str]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        _log.error("No se pudo leer fichero %s: %s", path, exc)
        return None
    for line in raw.splitlines():
        t = line.strip()
        if t:
            return t
    return None


def _parse_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return max(minimum, default)
    try:
        return max(minimum, int(raw))
    except ValueError:
        return max(minimum, default)


def _bool_env(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return default


def _vault_auth_method() -> str:
    m = (os.getenv("VAULT_AUTH_METHOD") or "token").strip().lower()
    if m in ("", "token"):
        return "token"
    if m in ("kubernetes", "k8s"):
        return "kubernetes"
    if m in ("approle", "app-role"):
        return "approle"
    return m


def _k8s_jwt_path() -> str:
    return (
        os.getenv("VAULT_K8S_JWT_PATH") or "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ).strip()


def _k8s_jwt_ready() -> bool:
    p = Path(_k8s_jwt_path())
    try:
        return p.is_file() and p.stat().st_size > 0
    except OSError:
        return False


def _vault_kv_fully_configured() -> bool:
    addr = (os.getenv("VAULT_ADDR") or "").strip()
    kv_path = (os.getenv("VAULT_KV_PATH") or "").strip().strip("/")
    if not addr or not kv_path:
        return False
    method = _vault_auth_method()
    if method == "token":
        if _strip("VAULT_TOKEN"):
            return True
        tf = (os.getenv("VAULT_TOKEN_FILE") or "").strip()
        return bool(tf and _read_first_non_empty_line(tf))
    if method == "kubernetes":
        role = (os.getenv("VAULT_K8S_ROLE") or "").strip()
        return bool(role and _k8s_jwt_ready())
    if method == "approle":
        role_id = (os.getenv("VAULT_APPROLE_ROLE_ID") or "").strip()
        if not role_id:
            return False
        if _strip("VAULT_APPROLE_SECRET_ID"):
            return True
        sf = (os.getenv("VAULT_APPROLE_SECRET_ID_FILE") or "").strip()
        return bool(sf and _read_first_non_empty_line(sf))
    return False


def _aws_secrets_fully_configured() -> bool:
    return bool((os.getenv("AWS_SECRETS_MANAGER_SECRET_ID") or "").strip())


class EnvSecretManager(SecretManagerService):
    """Backend por defecto: Railway / Docker / .env inyectados en el proceso."""

    def get_stripe_secret_key(self) -> Optional[str]:
        return _strip("STRIPE_SECRET_KEY")

    def get_stripe_webhook_secret(self) -> Optional[str]:
        return _strip("STRIPE_WEBHOOK_SECRET")

    def get_gocardless_access_token(self) -> Optional[str]:
        return _strip("GOCARDLESS_ACCESS_TOKEN")

    def get_gocardless_secret_id(self) -> Optional[str]:
        return _strip("GOCARDLESS_SECRET_ID")

    def get_gocardless_secret_key(self) -> Optional[str]:
        return _strip("GOCARDLESS_SECRET_KEY")

    def get_gocardless_webhook_secret(self) -> Optional[str]:
        return _strip("GOCARDLESS_WEBHOOK_SECRET")

    def get_jwt_secret_key(self) -> str:
        key = _strip("JWT_SECRET_KEY") or _strip("JWT_SECRET")
        if key:
            return key
        from app.core.config import get_settings

        return get_settings().JWT_SECRET_KEY

    def get_gocardless_env(self) -> str:
        raw = (os.getenv("GOCARDLESS_ENV") or "sandbox").strip().lower()
        return raw if raw in ("sandbox", "live") else "sandbox"

    def list_fernet_pii_raw_keys(self, *, include_previous: bool) -> tuple[str, ...]:
        ordered: list[str] = []
        for name in ("PII_ENCRYPTION_KEY", "FERNET_PII_KEY"):
            v = _strip(name)
            if v and v not in ordered:
                ordered.append(v)
        if include_previous:
            for name in ("PII_ENCRYPTION_KEY_PREVIOUS", "FERNET_PII_KEY_PREVIOUS"):
                v = _strip(name)
                if v and v not in ordered:
                    ordered.append(v)
        return tuple(ordered)

    def list_fernet_storage_raw_keys(self, *, include_previous: bool) -> tuple[str, ...]:
        ordered: list[str] = []
        primary = _strip("ENCRYPTION_KEY")
        if primary:
            ordered.append(primary)
        if include_previous:
            prev = _strip("ENCRYPTION_KEY_PREVIOUS")
            if prev and prev not in ordered:
                ordered.append(prev)
        for name in ("ENCRYPTION_SECRET_KEY", "BANK_TOKEN_ENCRYPTION_KEY"):
            v = _strip(name)
            if v and v not in ordered:
                ordered.append(v)
        return tuple(ordered)

    def get_openai_api_key(self) -> Optional[str]:
        return _strip("OPENAI_API_KEY")

    def get_anthropic_api_key(self) -> Optional[str]:
        return _strip("ANTHROPIC_API_KEY") or _strip("CLAUDE_API_KEY")

    def get_google_gemini_api_key(self) -> Optional[str]:
        return _strip("GEMINI_API_KEY") or _strip("GOOGLE_API_KEY")

    def get_azure_openai_api_key(self) -> Optional[str]:
        return _strip("AZURE_API_KEY") or _strip("AZURE_OPENAI_API_KEY")

    def get_azure_document_intelligence_endpoint(self) -> Optional[str]:
        return _strip("AZURE_ENDPOINT")

    def get_azure_document_intelligence_key(self) -> Optional[str]:
        return _strip("AZURE_KEY")


class JsonMapSecretManager(SecretManagerService, ABC):
    """Lecturas desde un mapa JSON (Vault ``data`` o AWS ``SecretString`` JSON)."""

    def __init__(self, *, cache_ttl_seconds: int) -> None:
        self._cache_ttl = max(5, cache_ttl_seconds)
        self._lock = threading.Lock()
        self._cache_data: Optional[dict[str, Any]] = None
        self._cache_expires: float = 0.0
        self._cached_bump: int = -1

    def _payload(self) -> dict[str, Any]:
        bump = get_integration_secret_version()
        with self._lock:
            now = time.monotonic()
            if (
                self._cache_data is not None
                and now < self._cache_expires
                and self._cached_bump == bump
            ):
                return self._cache_data
            data = self._load_payload()
            self._cache_data = data
            self._cache_expires = now + self._cache_ttl
            self._cached_bump = bump
            return self._cache_data

    @abstractmethod
    def _load_payload(self) -> dict[str, Any]:
        """Carga el mapa clave → valor (sin registrar valores)."""

    def _get(self, key: str) -> Optional[str]:
        d = self._payload()
        v = d.get(key)
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    def get_stripe_secret_key(self) -> Optional[str]:
        return self._get("STRIPE_SECRET_KEY")

    def get_stripe_webhook_secret(self) -> Optional[str]:
        return self._get("STRIPE_WEBHOOK_SECRET")

    def get_gocardless_access_token(self) -> Optional[str]:
        return self._get("GOCARDLESS_ACCESS_TOKEN")

    def get_gocardless_secret_id(self) -> Optional[str]:
        return self._get("GOCARDLESS_SECRET_ID")

    def get_gocardless_secret_key(self) -> Optional[str]:
        return self._get("GOCARDLESS_SECRET_KEY")

    def get_gocardless_webhook_secret(self) -> Optional[str]:
        return self._get("GOCARDLESS_WEBHOOK_SECRET")

    def get_jwt_secret_key(self) -> str:
        key = self._get("JWT_SECRET_KEY") or self._get("JWT_SECRET")
        if key:
            return key
        from app.core.config import get_settings

        return get_settings().JWT_SECRET_KEY

    def get_gocardless_env(self) -> str:
        raw = (self._get("GOCARDLESS_ENV") or os.getenv("GOCARDLESS_ENV") or "sandbox").strip().lower()
        return raw if raw in ("sandbox", "live") else "sandbox"

    def list_fernet_pii_raw_keys(self, *, include_previous: bool) -> tuple[str, ...]:
        d = self._payload()
        ordered: list[str] = []

        def take(name: str) -> None:
            v = d.get(name)
            if v is None:
                return
            s = str(v).strip()
            if s and s not in ordered:
                ordered.append(s)

        for name in ("PII_ENCRYPTION_KEY", "FERNET_PII_KEY"):
            take(name)
        if include_previous:
            for name in ("PII_ENCRYPTION_KEY_PREVIOUS", "FERNET_PII_KEY_PREVIOUS"):
                take(name)
        return tuple(ordered)

    def list_fernet_storage_raw_keys(self, *, include_previous: bool) -> tuple[str, ...]:
        d = self._payload()
        ordered: list[str] = []

        def take(name: str) -> None:
            v = d.get(name)
            if v is None:
                return
            s = str(v).strip()
            if s and s not in ordered:
                ordered.append(s)

        take("ENCRYPTION_KEY")
        if include_previous:
            take("ENCRYPTION_KEY_PREVIOUS")
        for name in ("ENCRYPTION_SECRET_KEY", "BANK_TOKEN_ENCRYPTION_KEY"):
            take(name)
        return tuple(ordered)

    def get_openai_api_key(self) -> Optional[str]:
        return self._get("OPENAI_API_KEY")

    def get_anthropic_api_key(self) -> Optional[str]:
        return self._get("ANTHROPIC_API_KEY") or self._get("CLAUDE_API_KEY")

    def get_google_gemini_api_key(self) -> Optional[str]:
        return self._get("GEMINI_API_KEY") or self._get("GOOGLE_API_KEY")

    def get_azure_openai_api_key(self) -> Optional[str]:
        return self._get("AZURE_API_KEY") or self._get("AZURE_OPENAI_API_KEY")

    def get_azure_document_intelligence_endpoint(self) -> Optional[str]:
        return self._get("AZURE_ENDPOINT")

    def get_azure_document_intelligence_key(self) -> Optional[str]:
        return self._get("AZURE_KEY")


class VaultKvSecretManager(JsonMapSecretManager):
    """
    KV v2 de Vault. ``VAULT_AUTH_METHOD``: ``token`` | ``kubernetes`` | ``approle``.
    Ante HTTP 403 se re-autentica una vez y se reintenta la lectura.
    """

    def __init__(self) -> None:
        super().__init__(cache_ttl_seconds=_parse_int_env("VAULT_CACHE_TTL_SECONDS", 120, minimum=5))
        self._addr = (os.getenv("VAULT_ADDR") or "").strip().rstrip("/")
        self._kv_mount = (os.getenv("VAULT_KV_MOUNT") or "secret").strip().strip("/")
        self._kv_path = (os.getenv("VAULT_KV_PATH") or "").strip().strip("/")
        self._namespace = (os.getenv("VAULT_NAMESPACE") or "").strip() or None
        self._timeout = max(1, _parse_int_env("VAULT_HTTP_TIMEOUT_SECONDS", 30, minimum=1))
        self._auth_method = _vault_auth_method()

        verify: bool | str = True
        ca = (os.getenv("VAULT_CA_CERT") or "").strip()
        if ca:
            verify = ca
        elif not _bool_env("VAULT_TLS_VERIFY", True):
            verify = False
            _log.warning("VAULT_TLS_VERIFY desactivado; solo en entornos controlados")

        self._client = hvac.Client(
            url=self._addr,
            namespace=self._namespace,
            verify=verify,
            timeout=self._timeout,
        )
        self._authenticate()

    def _assign_token_from_response(self, resp: Any) -> None:
        auth = (resp or {}).get("auth") or {}
        tok = auth.get("client_token")
        if not tok or not str(tok).strip():
            raise RuntimeError("Vault auth: la respuesta no incluye client_token válido")
        self._client.token = str(tok).strip()

    def _authenticate(self) -> None:
        if self._auth_method == "token":
            token = _strip("VAULT_TOKEN")
            if not token:
                tf = (os.getenv("VAULT_TOKEN_FILE") or "").strip()
                token = _read_first_non_empty_line(tf) if tf else None
            if not token:
                raise RuntimeError("Vault token: defina VAULT_TOKEN o VAULT_TOKEN_FILE válido")
            self._client.token = token
            return
        if self._auth_method == "kubernetes":
            role = (os.getenv("VAULT_K8S_ROLE") or "").strip()
            if not role:
                raise RuntimeError("VAULT_K8S_ROLE es obligatorio con VAULT_AUTH_METHOD=kubernetes")
            jwt_path = _k8s_jwt_path()
            try:
                jwt = Path(jwt_path).read_text(encoding="utf-8").strip()
            except OSError:
                jwt = ""
            if not jwt:
                raise RuntimeError(f"No se pudo leer JWT de Kubernetes en {jwt_path}")
            try:
                resp = self._client.auth.kubernetes.login(role=role, jwt=jwt)
            except Exception as exc:
                _log.error("Vault kubernetes login falló (role=%s): %s", role, exc)
                raise RuntimeError("Vault kubernetes auth failed") from exc
            self._assign_token_from_response(resp)
            return
        if self._auth_method == "approle":
            role_id = (os.getenv("VAULT_APPROLE_ROLE_ID") or "").strip()
            if not role_id:
                raise RuntimeError("VAULT_APPROLE_ROLE_ID es obligatorio con VAULT_AUTH_METHOD=approle")
            secret_id = _strip("VAULT_APPROLE_SECRET_ID")
            if not secret_id:
                sf = (os.getenv("VAULT_APPROLE_SECRET_ID_FILE") or "").strip()
                secret_id = _read_first_non_empty_line(sf) if sf else None
            if not secret_id:
                raise RuntimeError(
                    "AppRole: defina VAULT_APPROLE_SECRET_ID o VAULT_APPROLE_SECRET_ID_FILE válido"
                )
            try:
                resp = self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            except Exception as exc:
                _log.error("Vault approle login falló: %s", exc)
                raise RuntimeError("Vault approle auth failed") from exc
            self._assign_token_from_response(resp)
            return
        raise RuntimeError(f"VAULT_AUTH_METHOD desconocido: {self._auth_method!r}")

    def _read_kv_once(self) -> dict[str, Any]:
        resp = self._client.secrets.kv.v2.read_secret_version(
            path=self._kv_path,
            mount_point=self._kv_mount,
        )
        inner = (resp or {}).get("data") or {}
        data = inner.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Vault KV v2: respuesta sin mapa data")
        return data

    def _load_payload(self) -> dict[str, Any]:
        try:
            try:
                return self._read_kv_once()
            except Forbidden:
                _log.warning("Vault KV v2 403; re-autenticando y reintentando")
                self._authenticate()
                return self._read_kv_once()
        except Exception as exc:
            _log.error(
                "Fallo lectura Vault KV v2 (mount=%s path=%s): %s",
                self._kv_mount,
                self._kv_path,
                exc,
            )
            raise RuntimeError("Vault KV v2 read failed") from exc


class AwsSecretsManagerSecretManager(JsonMapSecretManager):
    """
    ``GetSecretValue`` sobre un secreto cuyo ``SecretString`` es JSON plano (mismas claves
    que ``EnvSecretManager``). Credenciales vía cadena estándar de boto3 (IRSA, ECS task role,
    etc.). Opcional ``AWS_REGION`` / ``AWS_DEFAULT_REGION``.
    """

    def __init__(self) -> None:
        super().__init__(
            cache_ttl_seconds=_parse_int_env("AWS_SECRETS_CACHE_TTL_SECONDS", 120, minimum=5),
        )
        import boto3

        self._secret_id = (os.getenv("AWS_SECRETS_MANAGER_SECRET_ID") or "").strip()
        if not self._secret_id:
            raise RuntimeError("AWS_SECRETS_MANAGER_SECRET_ID es obligatorio")
        self._region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip() or None
        self._client = boto3.client("secretsmanager", region_name=self._region)

    def _load_payload(self) -> dict[str, Any]:
        try:
            resp = self._client.get_secret_value(SecretId=self._secret_id)
        except Exception as exc:
            _log.error("AWS GetSecretValue falló (SecretId configurado, sin valor en log): %s", exc)
            raise RuntimeError("AWS Secrets Manager read failed") from exc
        raw_str = resp.get("SecretString")
        if raw_str is not None:
            data = json.loads(str(raw_str))
        else:
            raw_bin = resp.get("SecretBinary")
            if raw_bin is None:
                raise RuntimeError("AWS secret sin SecretString ni SecretBinary")
            if isinstance(raw_bin, str):
                payload = base64.b64decode(raw_bin)
            else:
                payload = bytes(raw_bin)
            data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("AWS secret JSON debe ser un objeto en la raíz")
        return data


class SaaSEnvSecretProvider(EnvSecretManager):
    """
    ``SECRET_MANAGER_BACKEND=vault`` sin API Vault completa: secretos solo por entorno
    (Agent injector, CSI, Railway, etc.).
    """

    def __init__(self) -> None:
        pass


@lru_cache(maxsize=1)
def get_secret_manager() -> SecretManagerService:
    backend = (os.getenv("SECRET_MANAGER_BACKEND") or "env").strip().lower()
    if backend in ("env", "railway", ""):
        return EnvSecretManager()
    if backend in ("aws", "secretsmanager"):
        global _aws_backend_warned
        if _aws_secrets_fully_configured():
            _log.info("SECRET_MANAGER_BACKEND=%s: AWS Secrets Manager", backend)
            return AwsSecretsManagerSecretManager()
        if not _aws_backend_warned:
            _log.warning(
                "SECRET_MANAGER_BACKEND=%s sin AWS_SECRETS_MANAGER_SECRET_ID; usando env",
                backend,
            )
            _aws_backend_warned = True
        return EnvSecretManager()
    if backend == "vault":
        global _vault_backend_warned
        if _vault_kv_fully_configured():
            mount = (os.getenv("VAULT_KV_MOUNT") or "secret").strip().strip("/")
            path = (os.getenv("VAULT_KV_PATH") or "").strip().strip("/")
            auth = _vault_auth_method()
            _log.info(
                "SECRET_MANAGER_BACKEND=vault: KV v2 mount=%s path=%s auth=%s",
                mount,
                path,
                auth,
            )
            return VaultKvSecretManager()
        if not _vault_backend_warned:
            _log.warning(
                "SECRET_MANAGER_BACKEND=vault: configuración incompleta (addr, path, auth); "
                "usando SaaSEnvSecretProvider (secretos vía entorno).",
            )
            _vault_backend_warned = True
        return SaaSEnvSecretProvider()
    if backend == "mock":
        return EnvSecretManager()
    _log.warning("SECRET_MANAGER_BACKEND=%s desconocido; usando env", backend)
    return EnvSecretManager()