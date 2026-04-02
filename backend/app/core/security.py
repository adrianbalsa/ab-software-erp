from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Final
from urllib.request import Request, urlopen

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


TOKEN_TYPE: Final[str] = "bearer"

_SUPABASE_JWT_AUDIENCE = "authenticated"
_DEFAULT_SUPABASE_JWKS_URL = "https://bmdzpbdyvzkycyfgndvd.supabase.co/auth/v1/.well-known/jwks.json"

# Argon2id vía passlib (argon2-cffi); alineado con recomendaciones actuales [OWASP / NIST-aligned].
_pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
    argon2__digest_size=32,
    argon2__salt_len=16,
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
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
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
    """Hash de contraseña con Argon2id (passlib)."""
    return _pwd_context.hash(plain_password)


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
            ok = _pwd_context.verify(plain_password, stored)
            if not ok:
                return False, False
            if _pwd_context.needs_update(stored):
                return True, True
            return True, False
        except Exception:
            return False, False

    if _LEGACY_SHA256_HEX_RE.match(stored):
        import hmac

        legacy = sha256_hex(plain_password)
        if hmac.compare_digest(stored.lower(), legacy.lower()):
            return True, True
        return False, False

    try:
        ok = _pwd_context.verify(plain_password, stored)
        if not ok:
            return False, False
        if _pwd_context.needs_update(stored):
            return True, True
        return True, False
    except Exception:
        return False, False


def create_access_token(
    *,
    subject: str,
    expires_minutes: int | None = None,
    empresa_id: str | None = None,
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
    rr = (rbac_role or "").strip().lower()
    if rr in ("owner", "traffic_manager", "driver", "cliente"):
        payload["rbac_role"] = rr
    av = (assigned_vehiculo_id or "").strip()
    if av:
        payload["assigned_vehiculo_id"] = av
    cj = (cliente_id or "").strip()
    if rr == "cliente" and cj:
        payload["cliente_id"] = cj
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
