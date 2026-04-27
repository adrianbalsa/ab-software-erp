from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Final
from urllib.request import Request, urlopen

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import get_settings


TOKEN_TYPE: Final[str] = "bearer"

_SUPABASE_JWT_AUDIENCE = "authenticated"
_DEFAULT_SUPABASE_JWKS_URL = "https://bmdzpbdyvzkycyfgndvd.supabase.co/auth/v1/.well-known/jwks.json"

# Argon2id vía argon2-cffi; parámetros alineados con el contexto anterior.
_password_hasher = PasswordHasher(
    memory_cost=65536,
    time_cost=3,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

# 64 hex chars = legacy SHA256(password) sin prefijo Argon2
_LEGACY_SHA256_HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def decode_access_token_payload(token: str) -> dict[str, Any]:
    """
    Verifica y decodifica el Bearer con `python-jose` (`jose.jwt`).

    1) JWT de **Supabase Auth** (HS256, aud=authenticated, iss=…/auth/v1).
    2) JWT de **POST /auth/login** (`sub` = usuario/email, firma con JWT_SECRET_KEY).

    El `sub` se cruza con `profiles` para obtener `empresa_id`.
    """
    settings = get_settings()
    base_url = settings.SUPABASE_URL.rstrip("/")
    expected_issuer = settings.SUPABASE_JWT_ISSUER or f"{base_url}/auth/v1"
    jwks_url = settings.SUPABASE_JWKS_URL or _DEFAULT_SUPABASE_JWKS_URL

    try:
        return _decode_supabase_es256_with_jwks(
            token=token,
            jwks_url=jwks_url,
            issuer=expected_issuer,
        )
    except JWTError:
        pass

    try:
        from app.services.secret_manager_service import get_secret_manager

        return jwt.decode(
            token,
            get_secret_manager().get_jwt_secret_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        pass

    raise ValueError("Token inválido o expirado")


@lru_cache(maxsize=1)
def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    req = Request(jwks_url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=5) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
        raise ValueError("JWKS inválido")
    return data


def _decode_supabase_es256_with_jwks(*, token: str, jwks_url: str, issuer: str) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise JWTError("Token sin 'kid' en header")

    jwks = _fetch_jwks(jwks_url)
    key = next((k for k in jwks["keys"] if isinstance(k, dict) and k.get("kid") == kid), None)

    if key is None:
        _fetch_jwks.cache_clear()
        jwks = _fetch_jwks(jwks_url)
        key = next((k for k in jwks["keys"] if isinstance(k, dict) and k.get("kid") == kid), None)

    if key is None:
        raise JWTError("No se encontró clave pública para 'kid'")

    return jwt.decode(
        token,
        key,
        algorithms=["ES256"],
        audience=_SUPABASE_JWT_AUDIENCE,
        issuer=issuer,
    )


def sha256_hex(value: str) -> str:
    """SHA-256 hex (legacy passwords + hash de refresh tokens opacos)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_refresh_token(raw_token: str) -> str:
    """Digest estable del refresh token antes de persistir (nunca guardar el token en claro)."""
    return sha256_hex(raw_token)


def hash_password_argon2id(plain_password: str) -> str:
    """Hash de contraseña con Argon2id."""
    return _password_hasher.hash(plain_password)


def password_hash_uses_legacy_sha256(stored_hash: str) -> bool:
    """True si ``stored_hash`` parece SHA-256 hex legacy de una contraseña."""
    return bool(_LEGACY_SHA256_HEX_RE.match((stored_hash or "").strip()))


def verify_password_against_stored(plain_password: str, stored_hash: str) -> tuple[bool, bool]:
    """
    Verifica contraseña contra el valor en `usuarios.password_hash`.

    Returns:
        (ok, needs_lazy_upgrade_to_argon2):
        - ``needs_lazy_upgrade_to_argon2`` True si validó contra SHA256 legacy (hay que re-escribir fila).
    """
    stored = (stored_hash or "").strip()
    if not stored:
        return False, False

    if stored.startswith("$argon2"):
        try:
            _password_hasher.verify(stored, plain_password)
            return True, _password_hasher.check_needs_rehash(stored)
        except VerifyMismatchError:
            return False, False
        except (InvalidHashError, VerificationError, ValueError):
            return False, False

    if password_hash_uses_legacy_sha256(stored):
        import hmac

        legacy = sha256_hex(plain_password)
        if hmac.compare_digest(stored.lower(), legacy.lower()):
            return True, True
        return False, False

    try:
        _password_hasher.verify(stored, plain_password)
        return True, _password_hasher.check_needs_rehash(stored)
    except VerifyMismatchError:
        return False, False
    except (InvalidHashError, VerificationError, ValueError):
        return False, False


def create_access_token(
    *,
    subject: str,
    expires_minutes: int | None = None,
    empresa_id: str | None = None,
    role: str | None = None,
    rbac_role: str | None = None,
    assigned_vehiculo_id: str | None = None,
    cliente_id: str | None = None,
) -> str:
    """
    Create a signed JWT access token.

    - subject: typically username/email.
    - empresa_id: codificado en el payload para contexto multi-tenant (complementa RLS).
    """
    settings = get_settings()
    exp_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=exp_minutes)

    payload: dict[str, object] = {
        "sub": subject,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    if empresa_id and str(empresa_id).strip():
        payload["empresa_id"] = str(empresa_id).strip()
    role_value = (role or "").strip().lower()
    if role_value in ("superadmin", "admin", "gestor", "transportista", "cliente", "developer"):
        payload["role"] = role_value
    rr = (rbac_role or "").strip().lower()
    if rr in ("owner", "admin", "traffic_manager", "driver", "cliente", "developer"):
        payload["rbac_role"] = rr
    av = (assigned_vehiculo_id or "").strip()
    if av:
        payload["assigned_vehiculo_id"] = av
    cj = (cliente_id or "").strip()
    if rr == "cliente" and cj:
        payload["cliente_id"] = cj
    from app.services.secret_manager_service import get_secret_manager

    return jwt.encode(payload, get_secret_manager().get_jwt_secret_key(), algorithm=settings.JWT_ALGORITHM)


_PASSWORD_RESET_TTL_MINUTES = 60


def create_password_reset_token(*, subject: str) -> str:
    """
    JWT de recuperación de contraseña (``typ=pwd_reset``), firmado con la misma clave que los access tokens.
    """
    settings = get_settings()
    sub = (subject or "").strip()
    if not sub:
        raise ValueError("password reset: subject vacío")
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=_PASSWORD_RESET_TTL_MINUTES)
    payload: dict[str, object] = {
        "sub": sub,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "typ": "pwd_reset",
    }
    from app.services.secret_manager_service import get_secret_manager

    return jwt.encode(payload, get_secret_manager().get_jwt_secret_key(), algorithm=settings.JWT_ALGORITHM)


def decode_password_reset_token(token: str) -> str | None:
    """Devuelve el ``username`` canónico si el token es válido y ``typ=pwd_reset``."""
    raw = (token or "").strip()
    if not raw:
        return None
    try:
        from app.services.secret_manager_service import get_secret_manager

        settings = get_settings()
        data = jwt.decode(
            raw,
            get_secret_manager().get_jwt_secret_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        return None
    if data.get("typ") != "pwd_reset":
        return None
    sub = str(data.get("sub") or "").strip()
    return sub or None


# --- Fernet (application-layer encryption for PII at rest) --------------------


def _fernet_from_raw_pii(raw: str) -> Fernet | None:
    if len(raw) != 44:
        return None
    try:
        return Fernet(raw.encode("ascii"))
    except Exception:
        return None


def _pii_fernets_encrypt_order() -> list[Fernet]:
    from app.services.secret_manager_service import get_secret_manager

    out: list[Fernet] = []
    for raw in get_secret_manager().list_fernet_pii_raw_keys(include_previous=False):
        f = _fernet_from_raw_pii(raw)
        if f is not None:
            out.append(f)
    return out


def _pii_fernets_decrypt_order() -> list[Fernet]:
    from app.services.secret_manager_service import get_secret_manager

    out: list[Fernet] = []
    seen_raw: set[str] = set()
    for raw in get_secret_manager().list_fernet_pii_raw_keys(include_previous=True):
        if raw in seen_raw:
            continue
        seen_raw.add(raw)
        f = _fernet_from_raw_pii(raw)
        if f is not None:
            out.append(f)
    return out


def fernet_encrypt_string(plain: str | None) -> str | None:
    """
    Cifra una cadena UTF-8 antes de persistir (NIF, IBAN, etc.).

    - ``None`` → ``None``; cadena vacía tras strip → ``""``.
    - Idempotente: si el valor ya parece token Fernet (prefijo ``gAAAA``), no se re-cifra.
    - Con ``PII_ENCRYPTION_KEY`` válida se usa Fernet directo; si no, ``encrypt_sensitive_data``
      (``ENCRYPTION_KEY`` / derivación legacy en ``app.core.encryption``).
    """
    if plain is None:
        return None
    s = str(plain).strip()
    if s == "":
        return ""
    if s.startswith("gAAAA"):
        return s
    ferns = _pii_fernets_encrypt_order()
    if ferns:
        return ferns[0].encrypt(s.encode("utf-8")).decode("ascii")
    from app.core.encryption import encrypt_sensitive_data

    return encrypt_sensitive_data(s)


def fernet_decrypt_string(cipher: str | None) -> str | None:
    """
    Descifra un token producido por ``fernet_encrypt_string``.

    Orden: Fernet con ``PII_ENCRYPTION_KEY`` → ``decrypt_sensitive_data`` (tolerante a legado/claro).
    """
    if cipher is None:
        return None
    if not isinstance(cipher, str):
        return str(cipher)
    s = cipher.strip()
    if s == "":
        return ""
    for f in _pii_fernets_decrypt_order():
        try:
            return f.decrypt(s.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeEncodeError):
            continue
    from app.core.encryption import decrypt_sensitive_data

    return decrypt_sensitive_data(s)
