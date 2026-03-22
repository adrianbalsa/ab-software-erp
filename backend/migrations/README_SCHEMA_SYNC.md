# Sincronización esquema DB ↔ backend FastAPI

## Columnas `empresas` (canónico: snake_case)

| Columna PostgreSQL | Modelos Pydantic (`schemas/empresa.py`) |
|--------------------|----------------------------------------|
| `nombre_legal` | `nombre_legal` |
| `nombre_comercial` | `nombre_comercial` |

Los **requests** JSON pueden usar también las claves legacy **`nombrelegal`** y **`nombrecomercial`** gracias a `validation_alias=AliasChoices(...)` y `model_config = ConfigDict(populate_by_name=True)`.

El script **`20260323_rename_columns_legacy_to_api.sql`** renombra columnas legadas `nombrecomercial` → `nombre_comercial` y `nombrelegal` → `nombre_legal` si aún existen sin guiones.

## Otras tablas consultadas

- **`clientes`:** el API usa `nombre` (coincide con Streamlit `portes_view` / `facturas_view`). No suele requerir RENAME.
- **`flota`:** ver comentarios en el mismo script SQL.

## Sesión / JWT y Railway

El backend **no** lee una variable llamada únicamente `JWT_SECRET` para arrancar si falta todo: la carga está en `app/core/config.py`:

1. **Obligatorio (login propio `/auth/login`):** `JWT_SECRET_KEY` **o** `JWT_SECRET` (cualquiera de los dos).
2. **Validación de tokens Supabase Auth:** `decode_access_token_payload` (`app/core/security.py`) intenta primero con **`SUPABASE_JWT_SECRET`** (issuer + audience `authenticated`). Si no defines `SUPABASE_JWT_SECRET`, se reutiliza el mismo valor que `JWT_SECRET_KEY`/`JWT_SECRET` — solo funciona si coincide con el JWT Secret del proyecto en Supabase Dashboard → Settings → API.

**Fallos típicos de “sesión”:**

| Síntoma | Causa probable |
|--------|----------------|
| App no arranca en Railway | Falta `JWT_SECRET_KEY` y `JWT_SECRET`. |
| 401 tras login con usuario/contraseña | Secreto distinto entre el que firmó el token y `JWT_SECRET_KEY`/`JWT_SECRET` en Railway. |
| 401 con token de Supabase Auth | `SUPABASE_JWT_SECRET` incorrecto o `SUPABASE_JWT_ISSUER` no coincide con el `iss` del JWT (dominio custom). |

Variables relacionadas: `JWT_ALGORITHM` (default `HS256`), `ACCESS_TOKEN_EXPIRE_MINUTES`, `SUPABASE_URL`.

## Facturas (D5) — PK numéricas

Los modelos Pydantic `FacturaOut` / `PorteOut.factura_id` asumen **`facturas.id` y `factura_rectificada_id` como BIGINT** (`int` en API). Las rutas `POST /facturas/{factura_id}/rectificar` y `GET /reports/facturas/{factura_id}/pdf` usan **`factura_id` entero**.

Si en tu instancia Supabase aún tienes `20260323_facturas_rectificativas_r1.sql` con `factura_rectificada_id UUID`, alinea la BD (migración a BIGINT y FK coherente) **antes** de exponer el API en producción; de lo contrario la validación Pydantic fallará al leer filas.

## UUIDs tenant / perfil (D1)

`UserOut.empresa_id` y `UserOut.usuario_id`, así como `empresa_id` en `porte`, `gasto` y `flota` (salida), usan tipo **`UUID`** en Pydantic para validar formato al parsear filas PostgREST.

## Maestras clientes / empresas (D2/D3)

- **`schemas/cliente.py`**: `ClienteOut` incluye `id`, `empresa_id` (UUID) y `deleted_at` opcional.
- **`schemas/empresa.py`**: `EmpresaOut` incluye `empresa_id` (igual que `id` en fila `empresas`) y `deleted_at`.
- Ejecutar **`20260326_master_soft_delete_clientes_empresas.sql`** si faltan columnas `deleted_at`.
- API: **`GET/POST/DELETE /clientes`** (`ClientesService`: listados con `filter_not_deleted`, borrado = `update deleted_at`).
- Admin: **`DELETE /admin/empresas/{id}`** archiva la empresa (soft delete); **`GET /admin/empresas`** solo filas con `deleted_at IS NULL`.
