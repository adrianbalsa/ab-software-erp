# Blindaje de identidad (Argon2id + refresh rotativo) [cite: 2026-03-22]

## Contraseñas (Argon2id)

- Nuevos hashes: **Argon2id**, `time_cost=3`, `memory_cost=65536` (KiB), `parallelism=4`.
- Hashes **SHA256 hex de 64 caracteres** en `usuarios.password_hash` siguen siendo válidos.
- Tras un login correcto con SHA256, el backend **reescribe** el hash a Argon2id (migración lazy).

## Refresh tokens

1. Ejecutar en Supabase: `migrations/20260322_refresh_tokens.sql`.
2. Cookie **HttpOnly**, **SameSite=Lax**; **Secure** en producción (o `COOKIE_SECURE=true`).
3. `POST /auth/refresh`: rota el refresh (el anterior queda `revoked`); devuelve nuevo `access_token` y nueva cookie.
4. Reutilización de un refresh **ya revocado** (fuera de la ventana de gracia) → evento en **Sentry** y revocación de **todas** las sesiones de ese usuario.

### Variables de entorno (opcional)

| Variable | Descripción |
|----------|-------------|
| `REFRESH_TOKEN_EXPIRE_DAYS` | Días de vida del refresh (default `14`). |
| `REFRESH_TOKEN_COOKIE_NAME` | Nombre de la cookie (default `abl_refresh`). |
| `REFRESH_REUSE_GRACE_SECONDS` | Segundos para ignorar carreras benignas en rotación (default `8`). |
| `COOKIE_SECURE` | `true`/`false` forzado; si no se define, `true` solo si `ENVIRONMENT=production`. |
| `COOKIE_DOMAIN` | Dominio de la cookie (p. ej. `.tudominio.com`) si front y API comparten parent domain. |

## Sesiones activas [cite: 2026-03-22]

- Migración: `migrations/20260324_refresh_tokens_ip_user_agent.sql` (`ip_address`, `user_agent`).
- `GET /auth/sessions` — lista sesiones (Bearer + cookie opcional para marcar `is_current`).
- `DELETE /auth/sessions/{id}` — revoca una sesión (solo si `user_id` del token = fila).
- `DELETE /auth/sessions/all` — revoca el resto; requiere cookie de refresh para excluir la actual.

## Frontend

- El login y las llamadas API deben usar `credentials: 'include'` para enviar la cookie cross-origin.
- `refreshAccessToken()` en `src/lib/api.ts` llama a `POST /auth/refresh`.
- Página `/perfil/seguridad` — gestión de sesiones en UI.

## Streamlit

- `services/auth_service.py` acepta **Argon2id** y SHA256 legacy (requiere `argon2-cffi` en el entorno raíz).
