from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.api import deps
from app.core.config import get_settings
from app.core.http_client_meta import get_client_ip
from app.core.security import TOKEN_TYPE, create_access_token
from app.schemas.auth import ActiveSessionOut, Token
from app.schemas.user import UserOut
from app.services.auth_service import AuthService
from app.services.refresh_token_service import RefreshTokenService


router = APIRouter()
_log = logging.getLogger(__name__)

_oauth: OAuth | None = None


def get_oauth() -> OAuth:
    """
    Cliente OAuth (authlib) para Google OIDC.
    Tras montar ``SessionMiddleware`` en la app, se puede usar ``authorize_redirect`` / ``authorize_access_token``.
    """
    global _oauth
    if _oauth is None:
        _oauth = OAuth()
        s = get_settings()
        if s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET:
            _oauth.register(
                name="google",
                client_id=s.GOOGLE_CLIENT_ID,
                client_secret=s.GOOGLE_CLIENT_SECRET,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
    return _oauth


async def _google_userinfo_from_token(
    *,
    token: dict[str, Any],
    oauth: OAuth,
    request: Request,
) -> dict[str, Any]:
    """Claims OIDC: userinfo en token, id_token parseado o endpoint userinfo."""
    ui = token.get("userinfo")
    if isinstance(ui, dict) and ui.get("sub"):
        return ui
    try:
        if token.get("id_token"):
            parsed = await oauth.google.parse_id_token(request, token)
            if isinstance(parsed, dict) and parsed.get("sub"):
                return parsed
    except Exception as exc:
        _log.debug("parse_id_token Google: %s", exc)
    try:
        resp = await oauth.google.get("userinfo", token=token)
        if resp is not None:
            data = resp.json()
            if isinstance(data, dict) and data.get("sub"):
                return data
    except Exception as exc:
        _log.warning("userinfo Google HTTP: %s", exc)
    return {}


def _attach_refresh_cookie(response: Response, *, raw_refresh: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_refresh,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(deps.get_auth_service_admin),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service_admin),
):
    """
    Devuelve ``access_token`` en JSON y fija el **refresh token** en cookie HttpOnly
    (Secure según entorno, SameSite=Lax). [cite: 2026-03-22]
    """
    user = await auth_service.authenticate(
        username=form_data.username,
        password=form_data.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    access_token = create_access_token(subject=user.username, empresa_id=user.empresa_id)
    await auth_service.ensure_empresa_context(empresa_id=user.empresa_id)

    raw_refresh: str | None = None
    max_age: int | None = None
    udb = await auth_service.get_user(username=form_data.username)
    if udb is not None and udb.id:
        try:
            raw_refresh, max_age = await refresh_service.issue_new_refresh(
                user_id=udb.id,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
        except Exception as exc:
            _log.warning("No se pudo emitir refresh token (¿migración SQL aplicada?): %s", exc)

    body = Token(
        access_token=access_token,
        token_type=TOKEN_TYPE,
        refresh_token=raw_refresh,
    ).model_dump()
    response = JSONResponse(content=body)
    if raw_refresh is not None and max_age is not None:
        _attach_refresh_cookie(response, raw_refresh=raw_refresh, max_age=max_age)

    return response


@router.post("/refresh")
async def refresh_session(
    request: Request,
    auth_service: AuthService = Depends(deps.get_auth_service_admin),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service_admin),
):
    """
    Rota el refresh token (cookie HttpOnly). El token anterior queda revocado.
    """
    settings = get_settings()
    raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)

    access_token, new_raw, max_age, user_out = await refresh_service.rotate(
        raw_refresh=raw,
        auth_service=auth_service,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await auth_service.ensure_empresa_context(empresa_id=user_out.empresa_id)

    body = Token(access_token=access_token, token_type=TOKEN_TYPE).model_dump()
    response = JSONResponse(content=body)
    _attach_refresh_cookie(response, raw_refresh=new_raw, max_age=max_age)
    return response


@router.get("/sessions", response_model=list[ActiveSessionOut])
async def list_active_sessions(
    request: Request,
    usuario_db_id: str | None = Depends(deps.get_usuario_db_id),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service),
) -> list[ActiveSessionOut]:
    """
    Sesiones activas del usuario autenticado (solo ``refresh_tokens`` con su ``user_id``).
    """
    if not usuario_db_id:
        return []
    settings = get_settings()
    raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    current_sid = await refresh_service.resolve_current_session_id(raw_refresh=raw)
    return await refresh_service.list_active_sessions_as_out(
        user_id=usuario_db_id,
        current_session_id=current_sid,
    )


@router.delete("/sessions/all", status_code=status.HTTP_200_OK)
async def revoke_other_sessions(
    request: Request,
    usuario_db_id: str | None = Depends(deps.get_usuario_db_id),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service),
) -> dict[str, int]:
    """
    Revoca todas las sesiones del usuario **excepto** la asociada a la cookie de refresh actual.
    Requiere enviar la cookie HttpOnly (mismo navegador donde hay sesión).
    """
    if not usuario_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay identificador de usuario para sesiones",
        )
    settings = get_settings()
    raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    current_sid = await refresh_service.resolve_current_session_id(raw_refresh=raw)
    if not current_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo identificar la sesión actual. Incluye la cookie de refresh o vuelve a iniciar sesión.",
        )
    n = await refresh_service.revoke_all_for_user_except(
        user_id=usuario_db_id,
        except_session_id=current_sid,
    )
    return {"revoked_count": n}


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def revoke_session(
    session_id: str,
    usuario_db_id: str | None = Depends(deps.get_usuario_db_id),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service),
) -> Response:
    """Revoca una sesión concreta (solo si pertenece al usuario)."""
    if not usuario_db_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")
    ok = await refresh_service.revoke_session_for_user(
        session_id=session_id,
        user_id=usuario_db_id,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/oauth/google/login")
async def oauth_google_login(request: Request) -> Any:
    """
    Inicia OIDC con Google: redirección a la pantalla de consentimiento.
    Authlib guarda ``state`` en la sesión firmada (CSRF). Scopes: openid, email, profile.
    """
    s = get_settings()
    if not (s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth no configurado",
        )
    if not s.GOOGLE_OAUTH_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOOGLE_OAUTH_REDIRECT_URI no configurado (URL absoluta del callback en Google Cloud)",
        )
    oauth = get_oauth()
    return await oauth.google.authorize_redirect(request, s.GOOGLE_OAUTH_REDIRECT_URI)


@router.get("/oauth/google/callback")
async def oauth_google_callback(
    request: Request,
    auth_service: AuthService = Depends(deps.get_auth_service_admin),
    refresh_service: RefreshTokenService = Depends(deps.get_refresh_token_service_admin),
) -> RedirectResponse:
    """
    Callback OAuth: valida ``state`` (sesión) con ``authorize_access_token``, obtiene identidad Google,
    vincula ``provider_subject`` en ``user_accounts`` si el email existe en ``usuarios``,
    emite access + refresh y redirige al frontend con el JWT en query (token URL-encoded).
    """
    s = get_settings()
    if not (s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth no configurado",
        )
    oauth = get_oauth()
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        # state inválido / manipulado o error del proveedor (Authlib valida state vs sesión)
        msg = getattr(exc, "description", None) or str(exc) or ""
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg.strip() or "OAuth inválido: state o parámetros incorrectos",
        ) from exc

    userinfo = await _google_userinfo_from_token(token=token, oauth=oauth, request=request)
    google_sub = str(userinfo.get("sub") or "").strip()
    email = str(userinfo.get("email") or "").strip().lower()
    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Respuesta de Google sin sub o email",
        )
    if userinfo.get("email_verified") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El email de Google no está verificado",
        )

    udb = await auth_service.get_usuario_by_email(email=email)
    if udb is None or not udb.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: el usuario debe estar dado de alta previamente o recibir una invitación",
        )

    try:
        await auth_service.link_google_account(user_id=udb.id, google_sub=google_sub)
    except ValueError as exc:
        if str(exc) == "google_already_linked":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta cuenta de Google ya está vinculada a otro usuario",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo vincular la cuenta de Google",
        ) from exc

    profile = await auth_service.get_profile_by_subject(subject=udb.username)
    if profile is not None and profile.empresa_id:
        user_out = profile
    elif udb.empresa_id:
        user_out = UserOut(
            username=udb.username,
            empresa_id=udb.empresa_id,
            rol=udb.rol,
            usuario_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sin empresa asignada",
        )

    access_token = create_access_token(subject=user_out.username, empresa_id=user_out.empresa_id)
    await auth_service.ensure_empresa_context(empresa_id=user_out.empresa_id)

    raw_refresh: str | None = None
    max_age: int | None = None
    try:
        raw_refresh, max_age = await refresh_service.issue_new_refresh(
            user_id=str(udb.id),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as exc:
        _log.warning("OAuth Google: no se pudo emitir refresh token: %s", exc)

    base = (s.PUBLIC_APP_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "PUBLIC_APP_URL u OFFICIAL_FRONTEND_ORIGIN no configurado: "
                "se requiere para redirigir tras OAuth Google"
            ),
        )

    # Token en query string (URL-safe); el front lo traslada a localStorage y limpia la URL.
    safe_token = quote(access_token, safe="")
    redirect_url = f"{base}/auth/callback?token={safe_token}"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    if raw_refresh is not None and max_age is not None:
        _attach_refresh_cookie(response, raw_refresh=raw_refresh, max_age=max_age)
    return response


@router.get("/oauth/google/status")
async def oauth_google_status() -> dict[str, bool | str]:
    """
    Comprueba si Google OIDC está configurado, callback URL y cliente authlib.
    """
    s = get_settings()
    get_oauth()
    configured = bool(
        s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET and s.GOOGLE_OAUTH_REDIRECT_URI
    )
    return {
        "google_oauth_configured": configured,
        "hint": "GET /auth/oauth/google/login inicia el flujo; SessionMiddleware firma la cookie de sesión (state).",
    }
