from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from typing import FrozenSet, Optional
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse


@dataclass(frozen=True, slots=True)
class Settings:
    PROJECT_NAME: str
    # development | production — CORS estricto, HSTS, etc.
    ENVIRONMENT: str
    SUPABASE_URL: str
    SUPABASE_KEY: str  # clave pública (anon) histórica
    SUPABASE_ANON_KEY: str  # misma que PostgREST con RLS (fallback: SUPABASE_KEY o env SUPABASE_ANON_KEY)
    SUPABASE_SERVICE_KEY: str
    # Secreto JWT Supabase (Dashboard → API). Opcional override de iss (dominio custom).
    SUPABASE_JWT_SECRET: str
    SUPABASE_JWT_ISSUER: str | None
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    REFRESH_TOKEN_COOKIE_NAME: str
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
    # GoCardless Bank Account Data (ex-Nordigen); opcional — sin credenciales no hay /bancos/*
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
    supabase_service_key = getenv("SUPABASE_SERVICE_KEY") or supabase_key

    # JWT (Railway/Vercel: usar JWT_SECRET_KEY; alias JWT_SECRET soportado)
    jwt_secret = getenv("JWT_SECRET_KEY") or getenv("JWT_SECRET")
    if not jwt_secret or not str(jwt_secret).strip():
        raise RuntimeError(
            "Falta secreto JWT para firmar/validar sesión: defina JWT_SECRET_KEY o JWT_SECRET en Railway. "
            "Para tokens de Supabase Auth use también SUPABASE_JWT_SECRET (Dashboard → API → JWT Secret). "
            "Ver backend/migrations/README_SCHEMA_SYNC.md"
        )
    jwt_secret = str(jwt_secret).strip()
    # Mismo secreto que en Supabase Dashboard → API → JWT Settings (HS256).
    # Si no se define, se reutiliza JWT_SECRET_KEY (solo válido si coinciden).
    supabase_jwt_secret = getenv("SUPABASE_JWT_SECRET") or jwt_secret
    supabase_jwt_issuer = getenv("SUPABASE_JWT_ISSUER")
    supabase_jwt_issuer = supabase_jwt_issuer.strip() if supabase_jwt_issuer else None

    # Optional / sensible defaults
    jwt_alg = getenv("JWT_ALGORITHM") or "HS256"
    expire_minutes = int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "15")
    refresh_days = int(getenv("REFRESH_TOKEN_EXPIRE_DAYS") or "7")
    refresh_cookie = (getenv("REFRESH_TOKEN_COOKIE_NAME") or "abl_refresh").strip() or "abl_refresh"
    reuse_grace = int(getenv("REFRESH_REUSE_GRACE_SECONDS") or "8")

    environment = (getenv("ENVIRONMENT") or "development").strip().lower()
    if environment not in ("development", "production"):
        environment = "development"

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

    session_secret_raw = getenv("SESSION_SECRET_KEY") or jwt_secret
    if not session_secret_raw or not str(session_secret_raw).strip():
        raise RuntimeError(
            "Falta SESSION_SECRET_KEY (o JWT_SECRET_KEY como respaldo) para SessionMiddleware / OAuth state."
        )
    session_secret = str(session_secret_raw).strip()

    database_url = _build_database_url(environment=environment)
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

    # ─── CORS: producción estricta (dominio oficial); desarrollo incluye localhost ───
    official = (getenv("OFFICIAL_FRONTEND_ORIGIN") or "").strip().rstrip("/")
    cors_extra_raw = getenv("CORS_ALLOW_ORIGINS") or ""

    if environment == "production":
        origins_set: set[str] = set()
        if official:
            origins_set.add(official)
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
            cors_allow_origin_regex = None
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
        SUPABASE_URL=supabase_url,
        SUPABASE_KEY=supabase_key,
        SUPABASE_ANON_KEY=supabase_anon_key,
        SUPABASE_SERVICE_KEY=supabase_service_key,
        SUPABASE_JWT_SECRET=supabase_jwt_secret,
        SUPABASE_JWT_ISSUER=supabase_jwt_issuer,
        JWT_SECRET_KEY=jwt_secret,
        JWT_ALGORITHM=jwt_alg,
        ACCESS_TOKEN_EXPIRE_MINUTES=expire_minutes,
        REFRESH_TOKEN_EXPIRE_DAYS=max(1, min(365, refresh_days)),
        REFRESH_TOKEN_COOKIE_NAME=refresh_cookie,
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
        AEAT_VERIFACTU_ENABLED=aeat_enabled,
        AEAT_VERIFACTU_USE_PRODUCTION=aeat_use_prod,
        AEAT_BLOQUEAR_PROD_EN_DESARROLLO=aeat_block_dev,
        AEAT_VERIFACTU_SUBMIT_URL_TEST=aeat_url_test,
        AEAT_VERIFACTU_SUBMIT_URL_PROD=aeat_url_prod,
        AEAT_CLIENT_CERT_PATH=aeat_cert,
        AEAT_CLIENT_KEY_PATH=aeat_key,
        AEAT_CLIENT_P12_PATH=aeat_p12,
        AEAT_CLIENT_P12_PASSWORD=aeat_p12_pwd,
    )

