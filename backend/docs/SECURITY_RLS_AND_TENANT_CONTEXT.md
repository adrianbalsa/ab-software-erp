# RLS, tenant context y backend

## Rol `service_role` vs JWT de usuario

El cliente Supabase del backend suele usar **`SUPABASE_SERVICE_KEY`**. En Supabase, las peticiones con **service role** **no aplican RLS** (bypass). Las políticas RLS y `set_empresa_context` protegen sobre todo:

- Acceso **directo** de clientes (PostgREST con JWT `anon` / `authenticated`).
- Futuros endpoints que usen la **anon key** o un cliente con rol de usuario.

Para que RLS sea la barrera principal, el backend debería usar el **JWT del usuario** contra PostgREST (o Edge Functions con claims), no la service key, en las rutas multi-tenant.

## `set_empresa_context` y peticiones HTTP

`set_empresa_context` establece `app.current_empresa_id` (u homólogo) en la sesión de Postgres **asociada a esa petición HTTP** a PostgREST. No hay garantía fuerte de “sesión sticky” si el pooler reutiliza conexiones de forma que mezcle contexto; por eso:

1. **`get_current_user`** llama a `ensure_empresa_context` tras resolver el perfil.
2. **`bind_write_context`** vuelve a llamar a `ensure_empresa_context` **justo antes** de handlers que hacen **INSERT/UPDATE/DELETE** (u operaciones equivalentes vía RPC que dependan del contexto).

Rutas que solo leen pueden depender de una sola llamada (la de `get_current_user`).

## Dependencias FastAPI

| Dependencia | Uso |
|-------------|-----|
| `get_current_user` | Autenticación + primera fijación de tenant. |
| `bind_write_context` | Igual que arriba + **segunda** llamada RPC antes de escrituras. |
| `require_admin_user` | Admin; lecturas admin. |
| `require_admin_write_user` | Admin + `bind_write_context` para POST/PATCH/DELETE admin. |

## Migración SQL

Ver `migrations/20260325_rls_granular_profiles_empresa_id_lock.sql`:

- Políticas explícitas **SELECT / INSERT / UPDATE / DELETE** para `portes`, `vehiculos` (si existe), `flota`, `auditoria` usando `public.app_current_empresa_id()`.
- Trigger en `profiles` que impide cambiar `empresa_id` salvo `service_role` o superadmin en JWT (`app_metadata.is_superadmin` o `app_metadata.role = superadmin`).

### Trigger: `EXECUTE PROCEDURE` vs `EXECUTE FUNCTION`

En PostgreSQL 14+, para funciones trigger se usa `EXECUTE FUNCTION ...`. En versiones anteriores, `EXECUTE PROCEDURE`. Si la migración falla al crear el trigger, ajusta la sintaxis a la de tu versión.
