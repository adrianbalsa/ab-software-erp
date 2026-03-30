-- >>> 26_20260429_vehiculos_gps_ultima.sql.json
-- Posición GPS en vivo (Fleet) — columnas en public.vehiculos
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS ultima_latitud numeric;
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS ultima_longitud numeric;
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS ultima_actualizacion_gps timestamptz;
    COMMENT ON COLUMN public.vehiculos.ultima_latitud IS 'Última latitud WGS84 reportada por el dispositivo.';
    COMMENT ON COLUMN public.vehiculos.ultima_longitud IS 'Última longitud WGS84 reportada por el dispositivo.';
    COMMENT ON COLUMN public.vehiculos.ultima_actualizacion_gps IS 'Marca temporal UTC del último ping GPS.';
  ELSE
    RAISE NOTICE 'Omitido GPS vehiculos: tabla public.vehiculos no existe';
  END IF;
END $$;


-- >>> 27_20260431_treasury_vencimientos.sql.json
-- Tesorería: vencimientos para proyección 30d y estado de pago en gastos (AP).
-- Compatible con despliegues que ya tienen `gastos` / `facturas`.

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fecha_vencimiento date;

COMMENT ON COLUMN public.facturas.fecha_vencimiento IS
  'Opcional: vencimiento de cobro; si NULL, la API usa fecha_emision + 30 días.';

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS fecha_vencimiento date;

COMMENT ON COLUMN public.gastos.fecha_vencimiento IS
  'Opcional: vencimiento de pago al proveedor; si NULL, la API usa fecha + 30 días.';

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS estado_pago text NOT NULL DEFAULT 'pendiente';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'gastos_estado_pago_check'
  ) THEN
    ALTER TABLE public.gastos
      ADD CONSTRAINT gastos_estado_pago_check
      CHECK (estado_pago IN ('pendiente', 'pagado'));
  END IF;
END $$;

COMMENT ON COLUMN public.gastos.estado_pago IS 'pendiente | pagado (cuentas por pagar).';


-- >>> 28_20260432_portes_cmr_conductor.sql.json
-- CMR: nombre del conductor (opcional; si NULL, el PDF deja la casilla en blanco).
ALTER TABLE public.portes ADD COLUMN IF NOT EXISTS conductor_nombre text;

COMMENT ON COLUMN public.portes.conductor_nombre IS
  'Nombre del conductor para carta de porte (CMR); opcional.';


-- >>> 29_20260433_clientes_cuenta_contable.sql.json
-- Cuenta contable PGC opcional por cliente (exportación a gestoría).
ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS cuenta_contable text;

COMMENT ON COLUMN public.clientes.cuenta_contable IS
  'Cuenta 430… si se informa; si NULL, la exportación genera 430 + sufijo determinista desde id.';


-- >>> 30_20260434_portes_firma_entrega_pod.sql.json
-- POD: firma consignatario, nombre, fecha entrega real, conductor explícito opcional.
-- RLS: permite UPDATE a conductores (vehículo asignado o conductor_asignado_id).

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS firma_consignatario_b64 text,
  ADD COLUMN IF NOT EXISTS firma_consignatario_url text,
  ADD COLUMN IF NOT EXISTS nombre_consignatario_final text,
  ADD COLUMN IF NOT EXISTS fecha_entrega_real timestamptz,
  ADD COLUMN IF NOT EXISTS conductor_asignado_id uuid REFERENCES public.profiles (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.portes.firma_consignatario_b64 IS 'Firma PNG/SVG en Base64 (data URL o raw).';
COMMENT ON COLUMN public.portes.firma_consignatario_url IS 'URL en Storage/CDN si la firma no se guarda en fila.';
COMMENT ON COLUMN public.portes.nombre_consignatario_final IS 'Nombre quien firma la entrega.';
COMMENT ON COLUMN public.portes.fecha_entrega_real IS 'Marca hora de la entrega confirmada.';
COMMENT ON COLUMN public.portes.conductor_asignado_id IS 'Opcional: perfil (profiles.id) asignado al porte si no basta vehículo.';

-- Estado: añadir Entregado (ciclo operativo previo a facturación).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'portes_estado_check' AND conrelid = 'public.portes'::regclass
  ) THEN
    ALTER TABLE public.portes DROP CONSTRAINT portes_estado_check;
  END IF;
END $$;

ALTER TABLE public.portes
  ADD CONSTRAINT portes_estado_check
  CHECK (estado IN ('pendiente', 'Entregado', 'facturado'));

-- Sesión: perfil actual (para RLS conductor explícito).
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL,
  p_profile_id uuid DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  r text;
BEGIN
  r := lower(trim(both from coalesce(p_rbac_role, 'owner')));
  IF r NOT IN ('owner', 'traffic_manager', 'driver') THEN
    r := 'owner';
  END IF;
  PERFORM set_config('app.rbac_role', r, true);
  IF p_assigned_vehiculo_id IS NULL THEN
    PERFORM set_config('app.assigned_vehiculo_id', '', true);
  ELSE
    PERFORM set_config('app.assigned_vehiculo_id', p_assigned_vehiculo_id::text, true);
  END IF;
  IF p_profile_id IS NULL THEN
    PERFORM set_config('app.current_profile_id', '', true);
  ELSE
    PERFORM set_config('app.current_profile_id', p_profile_id::text, true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid) IS
  'Fija app.rbac_role, app.assigned_vehiculo_id y app.current_profile_id (perfil JWT).';

CREATE OR REPLACE FUNCTION public.app_current_profile_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  s text;
BEGIN
  s := NULLIF(trim(both from current_setting('app.current_profile_id', true)), '');
  IF s IS NULL OR s = '' THEN
    RETURN NULL;
  END IF;
  RETURN s::uuid;
EXCEPTION
  WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;

-- Política UPDATE para conductores (firma entrega).
DROP POLICY IF EXISTS portes_update_driver_entrega ON public.portes;
CREATE POLICY portes_update_driver_entrega ON public.portes
  FOR UPDATE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'driver'
    AND (
      (
        vehiculo_id IS NOT NULL
        AND public.app_assigned_vehiculo_id() IS NOT NULL
        AND vehiculo_id = public.app_assigned_vehiculo_id()
      )
      OR (
        conductor_asignado_id IS NOT NULL
        AND conductor_asignado_id = public.app_current_profile_id()
        AND public.app_current_profile_id() IS NOT NULL
      )
    )
  )
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'driver'
    AND (
      (
        vehiculo_id IS NOT NULL
        AND public.app_assigned_vehiculo_id() IS NOT NULL
        AND vehiculo_id = public.app_assigned_vehiculo_id()
      )
      OR (
        conductor_asignado_id IS NOT NULL
        AND conductor_asignado_id = public.app_current_profile_id()
        AND public.app_current_profile_id() IS NOT NULL
      )
    )
  );


-- >>> 31_20260435_fix_rls_leaks.sql.json
-- =============================================================================
-- Cierre de fugas RLS multi-tenant (SaaS B2B)
-- =============================================================================
-- 1) maps_distance_cache: la política previa permitía a cualquier rol
--    `authenticated` leer/escribir TODA la caché (USING/WITH CHECK true),
--    filtrando mal entre tenants que usan JWT + clave anon en PostgREST.
--    Se aísla por empresa_id alineado con set_empresa_context / app_current_empresa_id().
--
-- 2) clientes: maestro por tenant con empresa_id en aplicación; se fuerza RLS
--    coherente con facturas/portes.
--
-- Requisito previo: funciones public.app_current_empresa_id() y contexto de sesión
-- (ver 20260324_rls_tenant_current_empresa.sql).
--
-- NOTA: TRUNCATE en maps_distance_cache invalida entradas globales previas (solo
--       km cacheados; se regeneran vía Google API). El backend debe enviar
--       empresa_id en upsert/select (maps_service).
-- =============================================================================

-- ─── maps_distance_cache: columna tenant + índice único + política estricta ───
DO $$
BEGIN
  IF to_regclass('public.maps_distance_cache') IS NOT NULL THEN
    DROP POLICY IF EXISTS maps_distance_cache_authenticated_all ON public.maps_distance_cache;

    TRUNCATE TABLE public.maps_distance_cache;

    -- Sustituir unicidad global por unicidad por tenant
    ALTER TABLE public.maps_distance_cache
      DROP CONSTRAINT IF EXISTS maps_distance_cache_cache_key_key;

    ALTER TABLE public.maps_distance_cache
      ADD COLUMN IF NOT EXISTS empresa_id uuid REFERENCES public.empresas (id) ON DELETE CASCADE;

    -- Filas ya truncadas; exigir tenant en nuevas filas
    ALTER TABLE public.maps_distance_cache
      ALTER COLUMN empresa_id SET NOT NULL;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_maps_distance_cache_empresa_cache_key
      ON public.maps_distance_cache (empresa_id, cache_key);

    ALTER TABLE public.maps_distance_cache ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS maps_distance_cache_tenant_all ON public.maps_distance_cache;
    CREATE POLICY maps_distance_cache_tenant_all ON public.maps_distance_cache
      FOR ALL
      TO authenticated
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    COMMENT ON COLUMN public.maps_distance_cache.empresa_id IS
      'Tenant propietario de la entrada de caché (aislamiento RLS).';
  ELSE
    RAISE NOTICE 'Omitido maps_distance_cache: tabla no existe';
  END IF;
END $$;

-- ─── clientes: RLS por empresa_id ───
DO $$
BEGIN
  IF to_regclass('public.clientes') IS NULL THEN
    RAISE NOTICE 'Omitido clientes: tabla no existe';
  ELSIF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'clientes' AND column_name = 'empresa_id'
  ) THEN
    RAISE NOTICE 'Omitido RLS clientes: falta columna empresa_id';
  ELSE
    ALTER TABLE public.clientes ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS clientes_tenant_all ON public.clientes;
    CREATE POLICY clientes_tenant_all ON public.clientes
      FOR ALL
      TO authenticated
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    COMMENT ON POLICY clientes_tenant_all ON public.clientes IS
      'SaaS: solo filas del tenant activo (app.current_empresa_id / app.empresa_id).';
  END IF;
END $$;


-- >>> 32_20260437_esg_auditoria_fuel_import.sql.json
-- =============================================================================
-- esg_auditoria: emisiones asociadas a combustible (fuel impact)
-- =============================================================================
-- Tabla auxiliar para registrar CO2 emitido por consumo de combustible,
-- vinculando cada ticket a `vehiculo_id` para reporting de ESG.
--
-- Multi-tenant: RLS por `empresa_id` usando `public.app_current_empresa_id()::text`.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.esg_auditoria (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  vehiculo_id uuid NOT NULL REFERENCES public.vehiculos(id) ON DELETE CASCADE,
  gasto_id text,
  fecha date NOT NULL,
  litros_consumidos numeric(18, 4) NOT NULL DEFAULT 0,
  co2_emitido_kg numeric(18, 6) NOT NULL DEFAULT 0,
  tipo_combustible text NOT NULL DEFAULT 'Diesel A',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_esg_auditoria_empresa_fecha
  ON public.esg_auditoria (empresa_id, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_esg_auditoria_empresa_vehiculo
  ON public.esg_auditoria (empresa_id, vehiculo_id);

ALTER TABLE public.esg_auditoria ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS esg_auditoria_tenant_all ON public.esg_auditoria;
CREATE POLICY esg_auditoria_tenant_all ON public.esg_auditoria
  FOR ALL
  TO authenticated
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

COMMENT ON TABLE public.esg_auditoria IS
  'Auxiliar ESG: emisiones CO2 por combustible consumido (audit/reporting) con aislamiento multi-tenant por empresa_id (RLS).';



-- >>> 33_20260438_audit_logs_append_only_security.sql.json
-- =============================================================================
-- Audit Logs inmutable (Append-Only) + Trigger genérico seguro
-- =============================================================================
-- Objetivos:
-- 1) Append-only: bloquear completamente UPDATE y DELETE sobre public.audit_logs
-- 2) Lectura: solo administradores del tenant (owner/traffic_manager) pueden hacer SELECT
-- 3) Función public.log_table_changes() (TRIGGER) conforme al contrato pedido:
--    - Leer TG_TABLE_NAME y TG_OP
--    - Extraer empresa_id usando public.app_current_empresa_id()::text
--      y si es NULL => fallback NEW.empresa_id / OLD.empresa_id
--    - old_data con row_to_json(OLD), new_data con row_to_json(NEW)
--    - usuario_id desde auth.uid()
-- 4) Re-enganchar triggers AFTER INSERT/UPDATE/DELETE en public.facturas y public.portes
--
-- Nota: El repo ya contiene un audit_logs (20260424_audit_logs_triggers.sql).
-- Esta migración lo "endurece" sin romper el contrato existente del API actual.
-- =============================================================================

BEGIN;

-- ─── 1) Columnas nominales según especificación (compatibles con el esquema actual) ───
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS tabla_afectada text;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS operacion text;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS registro_id uuid;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS usuario_id uuid;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS fecha timestamptz DEFAULT now();

-- ─── 2) RLS: lectura solo tenant-admin + bloqueo UPDATE/DELETE ───
-- SELECT: owner/traffic_manager + tenant activo (app_current_empresa_id)
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;

CREATE POLICY audit_logs_select_tenant_admin
  ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

-- Append-only: impedir UPDATE y DELETE de forma explícita (incluso si alguien tuviera privilegios).
DROP POLICY IF EXISTS audit_logs_no_update ON public.audit_logs;
CREATE POLICY audit_logs_no_update
  ON public.audit_logs
  FOR UPDATE
  USING (false)
  WITH CHECK (false);

DROP POLICY IF EXISTS audit_logs_no_delete ON public.audit_logs;
CREATE POLICY audit_logs_no_delete
  ON public.audit_logs
  FOR DELETE
  USING (false);

-- Refuerzo de privilegios a nivel GRANT/REVOKE.
REVOKE UPDATE, DELETE ON public.audit_logs FROM PUBLIC;
REVOKE UPDATE, DELETE ON public.audit_logs FROM authenticated;
REVOKE UPDATE, DELETE ON public.audit_logs FROM anon;

-- ─── 3) Función genérica de auditoría: public.log_table_changes() ───
-- Inserta en el esquema actual (table_name/record_id/action/changed_by/created_at)
-- y además rellena las columnas nominales (tabla_afectada/operacion/registro_id/usuario_id/fecha).
CREATE OR REPLACE FUNCTION public.log_table_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid;
  v_old jsonb;
  v_new jsonb;
  v_record_id_text text;
  v_record_id uuid;
  v_action_text text;
BEGIN
  v_action_text := TG_OP;

  -- 1) empresa_id: primero contexto de sesión, luego fallback NEW/OLD.
  v_empresa := NULLIF(public.app_current_empresa_id()::text, '')::uuid;

  IF TG_OP = 'INSERT' THEN
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(v_empresa, NEW.empresa_id);
  ELSIF TG_OP = 'UPDATE' THEN
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(v_empresa, NEW.empresa_id);
  ELSIF TG_OP = 'DELETE' THEN
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := COALESCE(v_empresa, OLD.empresa_id);
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  -- 2) registro_id: intentamos parsear id => uuid, y guardamos también en record_id (texto).
  v_record_id_text := COALESCE(
    (v_new ->> 'id'),
    (v_old ->> 'id')
  );

  IF v_record_id_text IS NULL OR length(trim(v_record_id_text)) = 0 THEN
    v_record_id := NULL;
  ELSE
    BEGIN
      v_record_id := v_record_id_text::uuid;
    EXCEPTION
      WHEN others THEN
        v_record_id := NULL;
    END;
  END IF;

  INSERT INTO public.audit_logs (
    empresa_id,
    table_name,
    record_id,
    action,
    old_data,
    new_data,
    changed_by,
    tabla_afectada,
    operacion,
    registro_id,
    usuario_id,
    fecha
  ) VALUES (
    v_empresa,
    TG_TABLE_NAME::varchar(128),
    COALESCE(v_record_id_text, gen_random_uuid()::text),
    v_action_text::public.audit_action,
    v_old,
    v_new,
    auth.uid(),
    TG_TABLE_NAME::text,
    v_action_text::text,
    v_record_id,
    auth.uid(),
    now()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.log_table_changes() IS
  'Trigger genérico Append-Only para audit_logs. Extrae empresa_id desde app_current_empresa_id() con fallback NEW/OLD.';

-- ─── 4) Aplicación del trigger ───
-- Facturas
DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas;
CREATE TRIGGER trg_audit_row_facturas
  AFTER INSERT OR UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.log_table_changes();

-- Portes
DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes;
CREATE TRIGGER trg_audit_row_portes
  AFTER INSERT OR UPDATE OR DELETE ON public.portes
  FOR EACH ROW
  EXECUTE PROCEDURE public.log_table_changes();

COMMIT;



-- >>> 34_20260439_audit_logs_select_strict_admin.sql.json
-- =============================================================================
-- Endurecer policy SELECT de audit_logs a "tenant admins" estrictos
-- (evitar fallback a owner si app.rbac_role no está seteado)
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS audit_logs_select_tenant_admin ON public.audit_logs;

CREATE POLICY audit_logs_select_tenant_admin
  ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND current_setting('app.rbac_role', true) IN ('owner', 'traffic_manager')
  );

COMMIT;



-- >>> 35_20260445_portes_dni_consignatario_pod.sql.json
-- DNI/NIE opcional del consignatario (POD).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS dni_consignatario text;

COMMENT ON COLUMN public.portes.dni_consignatario IS 'DNI/NIE del consignatario (opcional, entrega POD).';


-- >>> 36_20260447_portal_onboarding_risk_acceptance.sql.json
-- Onboarding B2B (portal cliente): base de riesgo + aceptación legal explícita.
-- Compatibilidad: todos los cambios son idempotentes.

-- 1) Extiende el enum de auditoría para eventos de onboarding.
ALTER TYPE public.audit_action ADD VALUE IF NOT EXISTS 'INVITE_SENT';
ALTER TYPE public.audit_action ADD VALUE IF NOT EXISTS 'RISK_ACCEPTED';

-- 2) Señales de riesgo en clientes (MVP).
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS limite_credito numeric(12,2) NOT NULL DEFAULT 3000,
  ADD COLUMN IF NOT EXISTS has_payment_history boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.clientes.limite_credito IS
  'Límite de crédito definido por operación/comercial para evaluar riesgo y exposición.';
COMMENT ON COLUMN public.clientes.has_payment_history IS
  'TRUE cuando existe historial de pagos operativo verificable para el cliente.';

-- 3) Evidencia de aceptación legal en onboarding (portal).
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS riesgo_aceptado boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS riesgo_aceptado_at timestamptz;

COMMENT ON COLUMN public.clientes.riesgo_aceptado IS
  'Aceptación explícita del cliente de la evaluación de riesgo y cobro automático SEPA.';
COMMENT ON COLUMN public.clientes.riesgo_aceptado_at IS
  'Timestamp UTC de aceptación legal en el portal cliente.';

-- Índice parcial para panel operativo (pendientes de aceptación).
CREATE INDEX IF NOT EXISTS idx_clientes_riesgo_aceptado_false
  ON public.clientes (empresa_id, created_at DESC)
  WHERE riesgo_aceptado = false;



-- >>> 37_20260501_add_portes_co2_kg.sql.json
-- Campo de emisiones simplificado para reportes financieros ESG.
alter table if exists public.portes
add column if not exists co2_kg numeric;

-- Backfill inicial desde campo legacy si existe valor.
update public.portes
set co2_kg = coalesce(co2_kg, co2_emitido)
where co2_kg is null;


-- >>> 38_20260502_facturas_fingerprint_hash_chain.sql.json
-- Encadenamiento adicional de integridad (fingerprint_hash + previous_fingerprint)
alter table if exists public.facturas
add column if not exists fingerprint_hash text,
add column if not exists previous_fingerprint text;

create index if not exists idx_facturas_empresa_fingerprint_hash
  on public.facturas (empresa_id, fingerprint_hash);

-- Trigger de inmutabilidad reforzada:
-- si ya existe fingerprint_hash, no se permiten updates (excepto transición de finalización ya permitida).
create or replace function public.enforce_immutable_facturas()
returns trigger
language plpgsql
as $$
begin
  if current_setting('role', true) = 'service_role' then
    if tg_op = 'DELETE' then
      return old;
    end if;
    return new;
  end if;

  if tg_op = 'UPDATE' then
    if old.hash_registro is not null
       and length(trim(old.hash_registro::text)) > 0
       and coalesce(old.is_finalized, false) is false
       and coalesce(new.is_finalized, false) is true
       and new.fingerprint is not null
       and length(trim(new.fingerprint::text)) > 0
    then
      return new;
    end if;

    if old.fingerprint_hash is not null and length(trim(old.fingerprint_hash::text)) > 0 then
      raise exception 'FORBIDDEN_IMMUTABLE_FACTURA: UPDATE prohibido (fingerprint_hash ya fijado)';
    end if;

    if old.hash_registro is not null and length(trim(old.hash_registro::text)) > 0 then
      raise exception
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla facturas)';
    end if;
    return new;
  elsif tg_op = 'DELETE' then
    if coalesce(old.is_finalized, false) is true then
      raise exception
        'IMMUTABLE_ROW: DELETE prohibido para factura finalizada VeriFactu (tabla facturas)';
    end if;
    if old.hash_registro is not null and length(trim(old.hash_registro::text)) > 0 then
      raise exception
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla facturas)';
    end if;
    return old;
  end if;

  return coalesce(new, old);
end;
$$;


-- >>> 39_audit_rls_status.sql.json
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
