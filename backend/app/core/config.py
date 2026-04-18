from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import FrozenSet, Optional
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

_CURRENT_DIR = Path.cwd()
load_dotenv(dotenv_path=_CURRENT_DIR / ".env")
load_dotenv(dotenv_path=_CURRENT_DIR.parent / ".env")


class ConfigError(ValueError):
    """Configuración inválida o insuficiente para arrancar la aplicación."""


@dataclass(frozen=True, slots=True)
class Settings:
    PROJECT_NAME: str
    # development | production — CORS estricto, HSTS, etc.
    ENVIRONMENT: str
    # FastAPI/Starlette: en producción debe ser False (sin trazas de error detalladas al cliente).
    DEBUG: bool
    # TrustedHostMiddleware: hosts permitidos en cabecera Host (p. ej. api.midominio.com). "*" = cualquiera (solo desarrollo).
    ALLOWED_HOSTS: tuple[str, ...]
    SUPABASE_URL: str
    SUPABASE_KEY: str  # clave pública (anon) histórica
    SUPABASE_ANON_KEY: str  # misma que PostgREST con RLS (fallback: SUPABASE_KEY o env SUPABASE_ANON_KEY)
    SUPABASE_SERVICE_KEY: str
    # Validación JWT Supabase via JWKS (ECC/ES256). Opcional override de iss (dominio custom).
    SUPABASE_JWKS_URL: str
    SUPABASE_JWT_ISSUER: str | None
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    REFRESH_TOKEN_COOKIE_NAME: str
    ACCESS_TOKEN_COOKIE_NAME: str
    REFRESH_REUSE_GRACE_SECONDS: int
    COOKIE_SECURE: bool
    COOKIE_DOMAIN: str | None
    CORS_ALLOW_ORIGINS: FrozenSet[str]
    CORS_ALLOW_ORIGIN_REGEX: Optional[str]  # p. ej. previews *.vercel.app (allow_origin_regex)
    SENTRY_DSN: Optional[str]
    # Stripe Billing (opcional; sin clave los endpoints de pago responden 503)
    STRIPE_SECRET_KEY: Optional[str]
    STRIPE_WEBHOOK_SECRET: Optional[str]
    STRIPE_PRICE_STARTER: Optional[str]
    STRIPE_PRICE_PRO: Optional[str]
    STRIPE_PRICE_ENTERPRISE: Optional[str]
    PUBLIC_APP_URL: Optional[str]
    # Resend (Email Engine); opcional — sin clave no se envían correos
    RESEND_API_KEY: Optional[str]
    EMAIL_FROM_ADDRESS: Optional[str]
    # SMTP (facturación / envío manual de PDF); opcional — sin host no usa SMTP
    SMTP_HOST: Optional[str]
    SMTP_PORT: int
    SMTP_USER: Optional[str]
    SMTP_PASSWORD: Optional[str]
    # Remitente From para SMTP (si falta, se puede alinear con EMAIL_FROM_ADDRESS en get_settings)
    EMAILS_FROM_EMAIL: Optional[str]
    # GoCardless Bank Account Data (ex-Nordigen); opcional — sin credenciales no hay /api/v1/banking/*
    GOCARDLESS_SECRET_ID: Optional[str]
    GOCARDLESS_SECRET_KEY: Optional[str]
    # GoCardless Pro (pagos) — token API y entorno
    GOCARDLESS_ACCESS_TOKEN: Optional[str]
    GOCARDLESS_ENV: str
    # GoCardless Payments webhooks (firma HMAC-SHA256 del body crudo)
    GOCARDLESS_WEBHOOK_SECRET: Optional[str]
    # Fernet (44 chars base64 url-safe). Prioridad en ``app.core.encryption``: ENCRYPTION_KEY → ENCRYPTION_SECRET_KEY → …
    ENCRYPTION_KEY: Optional[str]
    # Alias / compatibilidad con despliegues existentes.
    ENCRYPTION_SECRET_KEY: Optional[str]
    # Alias histórico; si falta ENCRYPTION_SECRET_KEY, se usa para cifrar requisition_id / tokens.
    BANK_TOKEN_ENCRYPTION_KEY: Optional[str]
    # SQLAlchemy / Postgres (opcional). En producción suele apuntar a PgBouncer :6432.
    DATABASE_URL: Optional[str]
    # Redis (rate limiting, colas); opcional — sin URL el rate limit usa almacenamiento en memoria.
    REDIS_URL: Optional[str]
    # Google OAuth (authlib OIDC); opcional — sin credenciales no hay flujo /auth/oauth/google/*
    GOOGLE_CLIENT_ID: Optional[str]
    GOOGLE_CLIENT_SECRET: Optional[str]
    # URL absoluta registrada en Google Cloud (p. ej. https://api.dominio.com/auth/oauth/google/callback)
    GOOGLE_OAUTH_REDIRECT_URI: Optional[str]
    # Firma de cookies de sesión (OAuth state/nonce); en producción conviene rotación independiente del JWT
    SESSION_SECRET_KEY: str
    # Google Maps Platform (servidor: Geocoding, Distance Matrix, Routes v2). Único nombre soportado: ``Maps_API_KEY``.
    maps_api_key: Optional[str]
    # AEAT VeriFactu / SIF (opcional; sin activar no se llama a la AEAT)
    AEAT_VERIFACTU_ENABLED: bool
    AEAT_VERIFACTU_USE_PRODUCTION: bool
    AEAT_BLOQUEAR_PROD_EN_DESARROLLO: bool
    AEAT_VERIFACTU_SUBMIT_URL_TEST: Optional[str]
    AEAT_VERIFACTU_SUBMIT_URL_PROD: Optional[str]
    AEAT_CLIENT_CERT_PATH: Optional[str]
    AEAT_CLIENT_KEY_PATH: Optional[str]
    AEAT_CLIENT_P12_PATH: Optional[str]
    AEAT_CLIENT_P12_PASSWORD: Optional[str]
    # Contraseña de la clave privada PEM (si el .key está cifrada); distinta de la del .p12
    AEAT_CLIENT_KEY_PASSWORD: Optional[str]
    # WSDL oficial SistemaFacturacion (Zeep); si falta, el cliente usa la URL por defecto AEAT.
    AEAT_VERIFACTU_WSDL_URL: Optional[str]
    # Si True, valida el XML bajo RegFactu contra SuministroLR.xsd antes del POST (exige payload oficial).
    AEAT_VERIFACTU_XSD_VALIDATE_REQUEST: bool
    # Override opcional de la URL del XSD SuministroLR (p. ej. espejo offline).
    AEAT_VERIFACTU_SUMINISTRO_LR_XSD_URL: Optional[str]


def _parse_debug_flag(*, environment: str) -> bool:
    """En producción siempre False. En desarrollo por defecto True salvo DEBUG=0/false."""
    if environment == "production":
        raw = getenv("DEBUG")
        if raw is not None and str(raw).strip().lower() in ("1", "true", "yes", "on"):
            raise RuntimeError("DEBUG no puede ser True cuando ENVIRONMENT=production")
        return False
    raw = getenv("DEBUG")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


_DEFAULT_PROD_ALLOWED_HOSTS: tuple[str, ...] = (
    "app.ablogistics-os.com",
    "api.ablogistics-os.com",
    "ablogistics-os.com",
    "www.ablogistics-os.com",
    # Permite despliegues en Vercel (p. ej. previews *.vercel.app) detrás de proxy.
    # TrustedHostMiddleware soporta sufijos con punto inicial para match por subdominio.
    ".vercel.app",
    "vercel.app",
    # Railway (hostname público del servicio; health interno usa /health sin validar Host).
    ".railway.app",
    "railway.app",
)


def _parse_allowed_hosts(*, environment: str) -> tuple[str, ...]:
    """
    Lista de Host permitidos para TrustedHostMiddleware.
    Producción: obligatorio vía ALLOWED_HOSTS (coma-separado) o API_PUBLIC_HOST.
    Se unen FQDN por defecto (doble dominio + API dedicada) con los definidos en env.
    Desarrollo: por defecto * (cualquier Host).
    """
    raw = (getenv("ALLOWED_HOSTS") or "").strip()
    if environment == "production":
        from_env = tuple(h.strip() for h in raw.split(",") if h.strip())
        api_host = (getenv("API_PUBLIC_HOST") or getenv("PUBLIC_API_HOST") or "").strip()
        merged_list = list(_DEFAULT_PROD_ALLOWED_HOSTS)
        if api_host:
            merged_list.append(api_host)
        merged_list.extend(from_env)
        # Sin duplicados, orden estable
        seen: set[str] = set()
        out: list[str] = []
        for h in merged_list:
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return tuple(out)
    if not raw:
        return ("*",)
    return tuple(h.strip() for h in raw.split(",") if h.strip())


def _require_env(name: str) -> str:
    value = getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _strip_pgbouncer_incompatible_query_params(url: str) -> str:
    """
    ``prepared_statements=false`` es la recomendación documental para PgBouncer (modo transaction)
    + algunos drivers; **psycopg2/psycopg3** rechazan ese parámetro en la URI. Si aparece en
    ``DATABASE_URL`` (p. ej. copiado de otro stack), se elimina; el efecto real se aplica en
    ``app.db.session`` vía ``connect_args`` (``prepare_threshold=0``).
    """
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k in ("prepared_statements", "prepare_threshold"):
        q.pop(k, None)
    new_query = urlencode(sorted(q.items()))
    return urlunparse(parts._replace(query=new_query))


def _build_database_url(*, environment: str) -> Optional[str]:
    """
    - ``DATABASE_URL`` explícita: se respeta (se limpian parámetros incompatibles con psycopg en URI).
    - Sin URL explícita: si existen ``POSTGRES_USER``, ``POSTGRES_PASSWORD`` y ``POSTGRES_DB``
      (o ``POSTGRES_DATABASE``), se construye:
      - **production**: host por defecto ``pgbouncer``, puerto ``6432``
      - **development**: host por defecto ``localhost``, puerto ``5432``
      (sobrescribibles con ``POSTGRES_HOST`` / ``POSTGRES_PORT``).

    Nota PgBouncer ``pool_mode=transaction``: no usar sentencias preparadas persistentes entre
    transacciones; con psycopg3 se fuerza ``prepare_threshold=0`` en ``create_engine(..., connect_args)``.
    """
    explicit = getenv("DATABASE_URL")
    if explicit and explicit.strip():
        return _strip_pgbouncer_incompatible_query_params(explicit.strip())

    user = getenv("POSTGRES_USER")
    password = getenv("POSTGRES_PASSWORD")
    db = getenv("POSTGRES_DB") or getenv("POSTGRES_DATABASE")
    if not user or not str(user).strip():
        return None
    if password is None or not str(password).strip():
        return None
    if not db or not str(db).strip():
        return None

    user = str(user).strip()
    password = str(password).strip()
    db = str(db).strip()

    host_raw = getenv("POSTGRES_HOST")
    port_raw = getenv("POSTGRES_PORT")
    if environment == "production":
        host = (host_raw or "pgbouncer").strip()
        port = (port_raw or "6432").strip()
    else:
        host = (host_raw or "localhost").strip()
        port = (port_raw or "5432").strip()

    driver = (getenv("SQLALCHEMY_DATABASE_DRIVER") or "postgresql+psycopg").strip()

    user_enc = quote_plus(user)
    password_enc = quote_plus(password)
    return f"{driver}://{user_enc}:{password_enc}@{host}:{port}/{db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Reuse your current env var names (as seen in Streamlit main.py)
    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_KEY")
    supabase_anon_raw = getenv("SUPABASE_ANON_KEY")
    supabase_anon_key = (supabase_anon_raw.strip() if supabase_anon_raw and supabase_anon_raw.strip() else supabase_key)
    supabase_service_key = (
        getenv("SUPABASE_SERVICE_KEY")
        or getenv("SUPABASE_SERVICE_ROLE_KEY")
        or supabase_key
    )

    supabase_jwks_url = (
        getenv("SUPABASE_JWKS_URL")
        or "https://bmdzpbdyvzkycyfgndvd.supabase.co/auth/v1/.well-known/jwks.json"
    )
    supabase_jwks_url = str(supabase_jwks_url).strip()
    # JWT local de la aplicación (Railway/Vercel: JWT_SECRET_KEY; alias JWT_SECRET soportado)
    jwt_secret_raw = getenv("JWT_SECRET_KEY") or getenv("JWT_SECRET")
    jwt_secret = str(jwt_secret_raw).strip() if jwt_secret_raw else ""
    if not jwt_secret and not supabase_jwks_url:
        raise RuntimeError(
            "Debe definir JWT_SECRET_KEY o SUPABASE_JWKS_URL para la validación de tokens."
        )
    supabase_jwt_issuer = getenv("SUPABASE_JWT_ISSUER")
    supabase_jwt_issuer = supabase_jwt_issuer.strip() if supabase_jwt_issuer else None

    # Optional / sensible defaults
    jwt_alg = getenv("JWT_ALGORITHM") or "HS256"
    expire_minutes = int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "15")
    refresh_days = int(getenv("REFRESH_TOKEN_EXPIRE_DAYS") or "7")
    refresh_cookie = (getenv("REFRESH_TOKEN_COOKIE_NAME") or "abl_refresh").strip() or "abl_refresh"
    access_cookie = (getenv("ACCESS_TOKEN_COOKIE_NAME") or "abl_auth_token").strip() or "abl_auth_token"
    reuse_grace = int(getenv("REFRESH_REUSE_GRACE_SECONDS") or "8")

    environment = (getenv("ENVIRONMENT") or "development").strip().lower()
    if environment not in ("development", "production"):
        environment = "development"

    debug = _parse_debug_flag(environment=environment)
    allowed_hosts = _parse_allowed_hosts(environment=environment)

    cookie_secure_env = getenv("COOKIE_SECURE")
    if cookie_secure_env is not None and cookie_secure_env.strip() != "":
        cookie_secure = cookie_secure_env.strip().lower() in ("1", "true", "yes")
    else:
        cookie_secure = environment == "production"
    cookie_domain_raw = getenv("COOKIE_DOMAIN")
    cookie_domain = cookie_domain_raw.strip() if cookie_domain_raw and cookie_domain_raw.strip() else None

    sentry_raw = getenv("SENTRY_DSN")
    sentry_dsn = sentry_raw.strip() if sentry_raw and sentry_raw.strip() else None

    def _opt(name: str) -> Optional[str]:
        v = getenv(name)
        return v.strip() if v and str(v).strip() else None

    stripe_secret = _opt("STRIPE_SECRET_KEY")
    stripe_wh = _opt("STRIPE_WEBHOOK_SECRET")
    stripe_ps = _opt("STRIPE_PRICE_STARTER")
    stripe_pp = _opt("STRIPE_PRICE_PRO")
    stripe_pe = _opt("STRIPE_PRICE_ENTERPRISE")
    public_app = _opt("PUBLIC_APP_URL") or _opt("OFFICIAL_FRONTEND_ORIGIN")
    resend_api_key = _opt("RESEND_API_KEY")
    email_from = _opt("EMAIL_FROM_ADDRESS")
    smtp_host = _opt("SMTP_HOST")
    smtp_port_raw = getenv("SMTP_PORT")
    try:
        smtp_port = int(str(smtp_port_raw).strip()) if smtp_port_raw and str(smtp_port_raw).strip() else 587
    except ValueError:
        smtp_port = 587
    smtp_user = _opt("SMTP_USER")
    smtp_password = _opt("SMTP_PASSWORD")
    emails_from_smtp = _opt("EMAILS_FROM_EMAIL") or email_from
    gc_sid = _opt("GOCARDLESS_SECRET_ID")
    gc_skey = _opt("GOCARDLESS_SECRET_KEY")
    gc_access_token = _opt("GOCARDLESS_ACCESS_TOKEN")
    gc_env_raw = (getenv("GOCARDLESS_ENV") or "sandbox").strip().lower()
    gc_env = gc_env_raw if gc_env_raw in ("sandbox", "live") else "sandbox"
    gc_wh_secret = _opt("GOCARDLESS_WEBHOOK_SECRET")
    enc_primary = _opt("ENCRYPTION_KEY")
    enc_secret = _opt("ENCRYPTION_SECRET_KEY")
    bank_enc = _opt("BANK_TOKEN_ENCRYPTION_KEY")
    google_cid = _opt("GOOGLE_CLIENT_ID")
    google_sec = _opt("GOOGLE_CLIENT_SECRET")
    google_redirect = _opt("GOOGLE_OAUTH_REDIRECT_URI")

    session_secret_raw = getenv("SESSION_SECRET_KEY")
    if session_secret_raw and str(session_secret_raw).strip():
        session_secret = str(session_secret_raw).strip()
    elif environment == "development":
        session_secret = "dev-session-secret-change-me"
    else:
        raise RuntimeError("Falta SESSION_SECRET_KEY en producción (Railway).")
    if not jwt_secret:
        jwt_secret = session_secret

    maps_api_key_raw = getenv("Maps_API_KEY")
    maps_api_key = (
        maps_api_key_raw.strip()
        if maps_api_key_raw and str(maps_api_key_raw).strip()
        else None
    )

    database_url = _build_database_url(environment=environment)
    # Due diligence / multi-réplica: en producción se exige URL explícita a Postgres.
    # No se admite despliegue solo con PostgREST (Supabase HTTP) sin conexión transaccional.
    if environment == "production":
        explicit_db_url = getenv("DATABASE_URL")
        if explicit_db_url is None or not str(explicit_db_url).strip():
            raise ConfigError(
                "ENVIRONMENT=production requiere DATABASE_URL no vacía (conexión directa a Postgres). "
                "El modo exclusivamente Supabase/REST sin DATABASE_URL está prohibido en producción."
            )
    redis_url = _opt("REDIS_URL")

    def _env_bool(name: str, default: bool = False) -> bool:
        raw = getenv(name)
        if raw is None or str(raw).strip() == "":
            return default
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    aeat_enabled = _env_bool("AEAT_VERIFACTU_ENABLED", False)
    aeat_use_prod = _env_bool("AEAT_VERIFACTU_USE_PRODUCTION", False)
    aeat_block_dev = _env_bool("AEAT_BLOQUEAR_PROD_EN_DESARROLLO", True)
    aeat_url_test = _opt("AEAT_VERIFACTU_SUBMIT_URL_TEST")
    aeat_url_prod = _opt("AEAT_VERIFACTU_SUBMIT_URL_PROD")
    aeat_cert = _opt("AEAT_CLIENT_CERT_PATH")
    aeat_key = _opt("AEAT_CLIENT_KEY_PATH")
    aeat_p12 = _opt("AEAT_CLIENT_P12_PATH")
    aeat_p12_pwd = _opt("AEAT_CLIENT_P12_PASSWORD")
    aeat_key_pwd = _opt("AEAT_CLIENT_KEY_PASSWORD")
    aeat_wsdl = _opt("AEAT_VERIFACTU_WSDL_URL")
    aeat_xsd_validate_req = _env_bool("AEAT_VERIFACTU_XSD_VALIDATE_REQUEST", True)
    aeat_lr_xsd = _opt("AEAT_VERIFACTU_SUMINISTRO_LR_XSD_URL")

    # ─── CORS: producción estricta (dominio oficial); desarrollo incluye localhost ───
    official = (getenv("OFFICIAL_FRONTEND_ORIGIN") or "").strip().rstrip("/")
    cors_extra_raw = getenv("CORS_ALLOW_ORIGINS") or ""

    _default_prod_cors = frozenset(
        {
            # Dominios oficiales para llamadas desde el frontend.
            "https://app.ablogistics-os.com",
            # API dedicada: permite llamadas cross-origin si algún flujo carga desde api.*.
            "https://api.ablogistics-os.com",
            "https://ablogistics-os.com",
            "https://www.ablogistics-os.com",
        }
    )
    if environment == "production":
        origins_set: set[str] = set(_default_prod_cors)
        if official:
            origins_set.add(official.rstrip("/"))
        for part in cors_extra_raw.split(","):
            o = part.strip().rstrip("/")
            if o:
                origins_set.add(o)
        if not origins_set:
            raise RuntimeError(
                "ENVIRONMENT=production requiere OFFICIAL_FRONTEND_ORIGIN y/o CORS_ALLOW_ORIGINS "
                "(lista HTTPS del front desplegado)."
            )
        cors_allow_origins = frozenset(origins_set)
        cors_re = getenv("CORS_ALLOW_ORIGIN_REGEX")
        if cors_re is None:
            # Permite builds/previews de Vercel en caso de que el tráfico llegue desde *.vercel.app.
            cors_allow_origin_regex = r"^https://[\w.-]+\.vercel\.app$"
        else:
            s = cors_re.strip()
            cors_allow_origin_regex = None if s in ("", "0") else s
    else:
        dev_defaults = (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
        )
        origins_set = {o for o in dev_defaults}
        if cors_extra_raw.strip():
            for part in cors_extra_raw.split(","):
                o = part.strip().rstrip("/")
                if o:
                    origins_set.add(o)
        cors_allow_origins = frozenset(origins_set)
        cors_re = getenv("CORS_ALLOW_ORIGIN_REGEX")
        if cors_re is None:
            cors_allow_origin_regex = r"^https://[\w.-]+\.vercel\.app$"
        else:
            s = cors_re.strip()
            cors_allow_origin_regex = None if s in ("", "0") else s

    return Settings(
        PROJECT_NAME=getenv("PROJECT_NAME") or "AB Logistics OS API",
        ENVIRONMENT=environment,
        DEBUG=debug,
        ALLOWED_HOSTS=allowed_hosts,
        SUPABASE_URL=supabase_url,
        SUPABASE_KEY=supabase_key,
        SUPABASE_ANON_KEY=supabase_anon_key,
        SUPABASE_SERVICE_KEY=supabase_service_key,
        SUPABASE_JWKS_URL=supabase_jwks_url,
        SUPABASE_JWT_ISSUER=supabase_jwt_issuer,
        JWT_SECRET_KEY=jwt_secret,
        JWT_ALGORITHM=jwt_alg,
        ACCESS_TOKEN_EXPIRE_MINUTES=expire_minutes,
        REFRESH_TOKEN_EXPIRE_DAYS=max(1, min(365, refresh_days)),
        REFRESH_TOKEN_COOKIE_NAME=refresh_cookie,
        ACCESS_TOKEN_COOKIE_NAME=access_cookie,
        REFRESH_REUSE_GRACE_SECONDS=max(0, min(120, reuse_grace)),
        COOKIE_SECURE=cookie_secure,
        COOKIE_DOMAIN=cookie_domain,
        CORS_ALLOW_ORIGINS=cors_allow_origins,
        CORS_ALLOW_ORIGIN_REGEX=cors_allow_origin_regex,
        SENTRY_DSN=sentry_dsn,
        STRIPE_SECRET_KEY=stripe_secret,
        STRIPE_WEBHOOK_SECRET=stripe_wh,
        STRIPE_PRICE_STARTER=stripe_ps,
        STRIPE_PRICE_PRO=stripe_pp,
        STRIPE_PRICE_ENTERPRISE=stripe_pe,
        PUBLIC_APP_URL=public_app,
        RESEND_API_KEY=resend_api_key,
        EMAIL_FROM_ADDRESS=email_from,
        SMTP_HOST=smtp_host,
        SMTP_PORT=max(1, min(65535, smtp_port)),
        SMTP_USER=smtp_user,
        SMTP_PASSWORD=smtp_password,
        EMAILS_FROM_EMAIL=emails_from_smtp,
        GOCARDLESS_SECRET_ID=gc_sid,
        GOCARDLESS_SECRET_KEY=gc_skey,
        GOCARDLESS_ACCESS_TOKEN=gc_access_token,
        GOCARDLESS_ENV=gc_env,
        GOCARDLESS_WEBHOOK_SECRET=gc_wh_secret,
        ENCRYPTION_KEY=enc_primary,
        ENCRYPTION_SECRET_KEY=enc_secret,
        BANK_TOKEN_ENCRYPTION_KEY=bank_enc,
        DATABASE_URL=database_url,
        REDIS_URL=redis_url,
        GOOGLE_CLIENT_ID=google_cid,
        GOOGLE_CLIENT_SECRET=google_sec,
        GOOGLE_OAUTH_REDIRECT_URI=google_redirect,
        SESSION_SECRET_KEY=session_secret,
        maps_api_key=maps_api_key,
        AEAT_VERIFACTU_ENABLED=aeat_enabled,
        AEAT_VERIFACTU_USE_PRODUCTION=aeat_use_prod,
        AEAT_BLOQUEAR_PROD_EN_DESARROLLO=aeat_block_dev,
        AEAT_VERIFACTU_SUBMIT_URL_TEST=aeat_url_test,
        AEAT_VERIFACTU_SUBMIT_URL_PROD=aeat_url_prod,
        AEAT_CLIENT_CERT_PATH=aeat_cert,
        AEAT_CLIENT_KEY_PATH=aeat_key,
        AEAT_CLIENT_P12_PATH=aeat_p12,
        AEAT_CLIENT_P12_PASSWORD=aeat_p12_pwd,
        AEAT_CLIENT_KEY_PASSWORD=aeat_key_pwd,
        AEAT_VERIFACTU_WSDL_URL=aeat_wsdl,
        AEAT_VERIFACTU_XSD_VALIDATE_REQUEST=aeat_xsd_validate_req,
        AEAT_VERIFACTU_SUMINISTRO_LR_XSD_URL=aeat_lr_xsd,
    )


# Backward-compatible module-level settings instance.
settings = get_settings()

