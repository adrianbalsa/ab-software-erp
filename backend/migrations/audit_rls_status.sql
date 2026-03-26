-- =============================================================================
-- Auditoría RLS (solo lectura) — AB Logistics OS / Supabase Postgres
-- =============================================================================
-- Ejecutar en SQL Editor o psql contra la base del proyecto.
-- No modifica el esquema; sirve para revisiones pre-producción y cumplimiento SaaS.
--
-- Requisitos: PostgreSQL ≥ 10 (vista pg_policies con qual / with_check).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Tarea 1: Estado RLS por tabla (esquema public)
-- -----------------------------------------------------------------------------
-- has_rls_enabled     : relrowsecurity en pg_class
-- policies_count      : filas en pg_policies
-- missing_empresa_id  : TRUE si la tabla no tiene columna empresa_id y no está
--                       en la lista de exenciones (maestras / modelo distinto)
-- has_empresa_id_col  : existencia física de la columna (contexto)
-- exempt_category     : motivo de exclusión del alerta, si aplica
-- -----------------------------------------------------------------------------

WITH exempt AS (
  SELECT *
  FROM (VALUES
    ('empresas',              'maestra_tenant_root'),
    ('usuarios',              'auth_usuarios_sin_empresa_id_directo'),
    ('refresh_tokens',        'sesion_por_user_id'),
    ('spatial_ref_sys',       'postgis_sistema'),
    ('geometry_columns',      'postgis_catalogo'),
    ('geography_columns',     'postgis_catalogo'),
    ('schema_migrations',     'herramienta_migraciones')
  ) AS t(table_name, exempt_category)
),
public_tables AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    c.oid     AS table_oid,
    c.relrowsecurity AS has_rls_enabled,
    c.relforcerowsecurity AS rls_force
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relkind = 'r'
    AND c.relname NOT LIKE 'pg\_%' ESCAPE '\'
)
SELECT
  pt.schema_name,
  pt.table_name,
  pt.has_rls_enabled,
  pt.rls_force AS rls_force_for_table_owner,
  COALESCE(
    (SELECT count(*)::integer
     FROM pg_policies pol
     WHERE pol.schemaname = pt.schema_name
       AND pol.tablename = pt.table_name),
    0
  ) AS policies_count,
  EXISTS (
    SELECT 1
    FROM information_schema.columns col
    WHERE col.table_schema = pt.schema_name
      AND col.table_name = pt.table_name
      AND col.column_name = 'empresa_id'
  ) AS has_empresa_id_col,
  (
    NOT EXISTS (
      SELECT 1
      FROM information_schema.columns col
      WHERE col.table_schema = pt.schema_name
        AND col.table_name = pt.table_name
        AND col.column_name = 'empresa_id'
    )
    AND e.table_name IS NULL
  ) AS missing_empresa_id,
  e.exempt_category
FROM public_tables pt
LEFT JOIN exempt e ON e.table_name = pt.table_name
ORDER BY
  missing_empresa_id DESC,
  policies_count ASC,
  pt.table_name;

-- -----------------------------------------------------------------------------
-- Tarea 2: Políticas críticas (qual / with_check) — revisión visual tenant
-- -----------------------------------------------------------------------------
-- Comprueba que USING / WITH CHECK acoten por app_current_empresa_id() o
-- auth.uid() según el modelo (p. ej. profiles).
-- -----------------------------------------------------------------------------

SELECT
  pol.schemaname,
  pol.tablename,
  pol.policyname,
  pol.cmd AS policy_command,
  pol.permissive,
  pol.roles,
  pol.qual AS using_expression,
  pol.with_check AS with_check_expression
FROM pg_policies pol
WHERE pol.schemaname = 'public'
  AND pol.tablename IN (
    'facturas',
    'portes',
    'clientes',
    'flota',
    'movimientos_bancarios',
    'vehiculos'
  )
ORDER BY pol.tablename, pol.policyname;

-- -----------------------------------------------------------------------------
-- Tarea 3 (informe): privilegios amplios anon / authenticated / PUBLIC
-- -----------------------------------------------------------------------------
-- Si aparecen GRANTs de INSERT/UPDATE/DELETE/TRUNCATE para anon en tablas de
-- negocio, revisar: sin políticas RLS adecuadas, el riesgo es alto.
-- -----------------------------------------------------------------------------

SELECT
  tp.grantee,
  tp.table_schema,
  tp.table_name,
  tp.privilege_type,
  (
    SELECT c.relrowsecurity
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = tp.table_schema
      AND c.relname = tp.table_name
      AND c.relkind = 'r'
    LIMIT 1
  ) AS table_has_rls
FROM information_schema.table_privileges tp
WHERE tp.table_schema = 'public'
  AND tp.grantee IN ('anon', 'authenticated', 'PUBLIC')
ORDER BY tp.grantee, tp.table_name, tp.privilege_type;
