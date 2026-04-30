-- Audit de privilegios peligrosos para gobernanza DDL.
-- Uso:
--   1) Ejecutar tal cual para revisar roles backend habituales.
--   2) Cambiar la lista en target_roles si el backend usa otro rol.

WITH target_roles(role_name) AS (
  VALUES
    ('authenticated'::name),
    ('service_role'::name)
),
target_tables AS (
  SELECT c.oid, n.nspname AS schema_name, c.relname AS table_name, pg_get_userbyid(c.relowner) AS owner_name
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'r'
    AND n.nspname = 'public'
    AND c.relname IN ('facturas', 'auditoria')
),
priv_matrix AS (
  SELECT
    r.role_name::text AS role_name,
    t.schema_name,
    t.table_name,
    t.owner_name,
    has_table_privilege(r.role_name, format('%I.%I', t.schema_name, t.table_name), 'SELECT') AS can_select,
    has_table_privilege(r.role_name, format('%I.%I', t.schema_name, t.table_name), 'INSERT') AS can_insert,
    has_table_privilege(r.role_name, format('%I.%I', t.schema_name, t.table_name), 'UPDATE') AS can_update,
    has_table_privilege(r.role_name, format('%I.%I', t.schema_name, t.table_name), 'DELETE') AS can_delete,
    has_table_privilege(r.role_name, format('%I.%I', t.schema_name, t.table_name), 'TRUNCATE') AS can_truncate,
    has_table_privilege(r.role_name, format('%I.%I', t.schema_name, t.table_name), 'TRIGGER') AS can_trigger,
    (
      t.owner_name = r.role_name::text
      OR pg_has_role(r.role_name, t.owner_name, 'MEMBER')
    ) AS can_drop
  FROM target_roles r
  CROSS JOIN target_tables t
)
SELECT
  role_name,
  schema_name,
  table_name,
  owner_name,
  can_select,
  can_insert,
  can_update,
  can_delete,
  can_truncate,
  can_trigger,
  can_drop,
  CASE
    WHEN can_truncate OR can_trigger OR can_drop THEN 'CRITICAL: DDL/DESTRUCTIVE PRIVILEGE PRESENT'
    ELSE 'OK: no TRUNCATE/TRIGGER/DROP path detected'
  END AS governance_status
FROM priv_matrix
ORDER BY role_name, table_name;

-- Vista detalle de grants explícitos (si existen), útil para trazabilidad.
SELECT
  grantee,
  table_schema,
  table_name,
  privilege_type,
  is_grantable
FROM information_schema.role_table_grants
WHERE grantee IN ('authenticated', 'service_role')
  AND table_schema = 'public'
  AND table_name IN ('facturas', 'auditoria')
ORDER BY grantee, table_name, privilege_type;
