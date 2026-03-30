-- >>> MIGRATION FILE: 04_20260322_auditoria_api_columns_facturas_immutability.sql.json
-- Producción VeriFactu: columnas usadas por la API y regla de inmutabilidad básica.
-- Ejecutar en Supabase SQL Editor (producción) tras las migraciones previas.

-- 1) Auditoría: columnas que inserta `AuditoriaService` / `VerifactuService.registrar_evento`
ALTER TABLE public.auditoria
  ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ;

COMMENT ON COLUMN public.auditoria.timestamp IS 'Duplicado opcional de fecha (ISO desde API)';

-- Si `cambios` es JSONB y la API envía texto, Postgres suele castear; si prefieres TEXT:
-- ALTER TABLE public.auditoria ALTER COLUMN cambios TYPE TEXT USING cambios::text;

-- 2) Inmutabilidad: no alterar huella/número de factura VeriFactu si el registro está bloqueado
CREATE OR REPLACE FUNCTION public.prevent_locked_factura_verifactu_mutate()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF COALESCE(OLD.bloqueado, FALSE) IS TRUE THEN
    IF NEW.hash_registro IS DISTINCT FROM OLD.hash_registro
       OR NEW.hash_factura IS DISTINCT FROM OLD.hash_factura
       OR NEW.num_factura IS DISTINCT FROM OLD.num_factura
       OR NEW.numero_factura IS DISTINCT FROM OLD.numero_factura
       OR NEW.numero_secuencial IS DISTINCT FROM OLD.numero_secuencial
       OR NEW.hash_anterior IS DISTINCT FROM OLD.hash_anterior
    THEN
      RAISE EXCEPTION 'Factura bloqueada (VeriFactu): no se permiten cambios en huella o numeración';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_verifactu_locked ON public.facturas;
CREATE TRIGGER trg_facturas_verifactu_locked
  BEFORE UPDATE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.prevent_locked_factura_verifactu_mutate();


-- >>> MIGRATION FILE: 05_20260322_refresh_tokens.sql.json
-- =============================================================================
-- Refresh tokens (rotación) + FK a usuarios [cite: 2026-03-22]
-- Ejecutar en Supabase SQL Editor (orden: después de public.usuarios).
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.usuarios (id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.refresh_tokens IS
  'Sesiones OAuth-style: hash del refresh token; rotación invalida fila previa.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash
  ON public.refresh_tokens (token_hash);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_active
  ON public.refresh_tokens (user_id)
  WHERE revoked = FALSE;

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
  ON public.refresh_tokens (user_id);


-- >>> MIGRATION FILE: 06_20260323_facturas_rectificativas_r1.sql.json
-- Rectificativas VeriFactu R1 [cite: 2026-03-22]
-- Vínculo a factura original sellada + motivo (texto libre para expediente).

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS factura_rectificada_id UUID REFERENCES public.facturas (id);

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS motivo_rectificacion TEXT;

COMMENT ON COLUMN public.facturas.factura_rectificada_id IS
  'Factura F1 (u original) que corrige esta R1; NULL en facturas normales.';
COMMENT ON COLUMN public.facturas.motivo_rectificacion IS
  'Motivo de la rectificación (VeriFactu / trazabilidad).';

CREATE INDEX IF NOT EXISTS idx_facturas_rectificada_id
  ON public.facturas (factura_rectificada_id)
  WHERE factura_rectificada_id IS NOT NULL;


-- >>> MIGRATION FILE: 07_20260323_rename_columns_legacy_to_api.sql.json
-- =============================================================================
-- Sincronización columnas PostgreSQL (producción) → nombres esperados por el
-- backend FastAPI / PostgREST (consultas en app/services/* y schemas Pydantic).
--
-- Empresas: el API y el Panel Admin usan snake_case (`nombre_legal`, `nombre_comercial`).
-- Si aún existen columnas legadas sin guiones (`nombrelegal`, `nombrecomercial`),
-- este bloque las renombra.
--
-- Ejecutar en Supabase SQL Editor (producción). Idempotente: no falla si ya
-- están alineados. Revisa vistas/materialized views que referencien los nombres
-- antiguos y recréalas si aplica.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- public.empresas
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'empresas'
  ) THEN
    -- nombrecomercial → nombre_comercial
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombrecomercial'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombre_comercial'
    ) THEN
      ALTER TABLE public.empresas RENAME COLUMN nombrecomercial TO nombre_comercial;
      RAISE NOTICE 'empresas: nombrecomercial → nombre_comercial';
    END IF;

    -- nombrelegal → nombre_legal
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombrelegal'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombre_legal'
    ) THEN
      ALTER TABLE public.empresas RENAME COLUMN nombrelegal TO nombre_legal;
      RAISE NOTICE 'empresas: nombrelegal → nombre_legal';
    END IF;
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- public.flota (esquema antiguo en supabase_schema.sql vs views/flota_view.py)
-- El API espera: vehiculo, matricula, precio_compra, km_actual, estado, tipo_motor
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'flota'
  ) THEN
    -- km_actuales → km_actual
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'km_actuales'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'km_actual'
    ) THEN
      ALTER TABLE public.flota RENAME COLUMN km_actuales TO km_actual;
      RAISE NOTICE 'flota: km_actuales → km_actual';
    END IF;
  END IF;
END $$;

-- Si tras los RENAME siguen faltando columnas que exige FlotaVehiculoOut, añádelas:
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS vehiculo text;
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS precio_compra numeric DEFAULT 0;
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS tipo_motor text;
-- Rellenar vehiculo desde marca/modelo legados si existían
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'marca'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'modelo'
  ) THEN
    UPDATE public.flota
    SET vehiculo = NULLIF(trim(both ' ' from concat_ws(' ', nullif(trim(marca), ''), nullif(trim(modelo), ''))), '')
    WHERE (vehiculo IS NULL OR trim(vehiculo) = '');
  END IF;
END $$;

COMMENT ON COLUMN public.flota.vehiculo IS 'Denominación del vehículo (API FastAPI / Streamlit flota_view)';


-- >>> MIGRATION FILE: 08_20260324_esg_certificacion_vw_emissions.sql.json
-- Certificación de emisiones (norma) en flota y vehículos; vista ESG.
-- Valores: Euro V, Euro VI, Electrico, Hibrido (default Euro VI).

ALTER TABLE public.vehiculos
  ADD COLUMN IF NOT EXISTS certificacion_emisiones text NOT NULL DEFAULT 'Euro VI';

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS certificacion_emisiones text NOT NULL DEFAULT 'Euro VI';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'vehiculos_certificacion_emisiones_check'
  ) THEN
    ALTER TABLE public.vehiculos
      ADD CONSTRAINT vehiculos_certificacion_emisiones_check
      CHECK (certificacion_emisiones IN ('Euro V', 'Euro VI', 'Electrico', 'Hibrido'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'flota_certificacion_emisiones_check'
  ) THEN
    ALTER TABLE public.flota
      ADD CONSTRAINT flota_certificacion_emisiones_check
      CHECK (certificacion_emisiones IN ('Euro V', 'Euro VI', 'Electrico', 'Hibrido'));
  END IF;
END $$;

COMMENT ON COLUMN public.vehiculos.certificacion_emisiones IS
  'Norma de emisiones (ESG auditoría): Euro V, Euro VI, Electrico, Hibrido';

COMMENT ON COLUMN public.flota.certificacion_emisiones IS
  'Norma de emisiones (ESG auditoría): Euro V, Euro VI, Electrico, Hibrido';

-- Detalle por porte con CO2 y certificación (filtrar por rango de fechas en consultas).
CREATE OR REPLACE VIEW public.vw_esg_emissions_summary AS
SELECT
  p.id AS porte_id,
  p.empresa_id,
  p.cliente_id,
  p.vehiculo_id,
  (p.fecha::date) AS fecha,
  COALESCE(p.co2_emitido, 0)::numeric AS co2_kg,
  COALESCE(v.certificacion_emisiones, f.certificacion_emisiones, 'Euro VI'::text) AS certificacion_emisiones
FROM public.portes p
LEFT JOIN public.vehiculos v
  ON v.id = p.vehiculo_id
  AND v.empresa_id = p.empresa_id
  AND v.deleted_at IS NULL
LEFT JOIN public.flota f
  ON f.id = p.vehiculo_id
  AND f.empresa_id = p.empresa_id
  AND f.deleted_at IS NULL
WHERE p.deleted_at IS NULL;

COMMENT ON VIEW public.vw_esg_emissions_summary IS
  'Portes con co2_kg y certificación (COALESCE vehiculos, flota, Euro VI). Filtrar fecha en WHERE.';


-- >>> MIGRATION FILE: 09_20260324_refresh_tokens_ip_user_agent.sql.json
-- Metadatos de sesión (IP + User-Agent) [cite: 2026-03-22]
ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS ip_address TEXT;

ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS user_agent TEXT;

COMMENT ON COLUMN public.refresh_tokens.ip_address IS 'IP del cliente al crear/rotar la sesión (mejor esfuerzo; detrás de proxy usar X-Forwarded-For).';
COMMENT ON COLUMN public.refresh_tokens.user_agent IS 'Cabecera User-Agent en login/refresh.';


-- >>> MIGRATION FILE: 10_20260324_rls_tenant_current_empresa.sql.json
-- =============================================================================
-- RLS multi-tenant: aislar filas por contexto de sesión
-- =============================================================================
-- Alineado con `set_empresa_context`: se publican **dos** claves de sesión para
-- máxima compatibilidad con código y documentación:
--   - app.empresa_id      (histórico en supabase_schema.sql)
--   - app.current_empresa_id (convención explícita solicitada)
--
-- El backend debe invocar `set_empresa_context` tras autenticación (ya implementado).
-- IMPORTANTE: El panel admin global en FastAPI suele usar la **service role** o
-- políticas que permitan lectura amplia; con JWT `anon` + RLS estricto, `/admin/*`
-- podría devolver filas vacías salvo que uses **service key** en el servidor o
-- políticas adicionales por rol. Revisa despliegue antes de activar en producción.
-- =============================================================================

-- Implementación TEXT (ids legacy no UUID).
CREATE OR REPLACE FUNCTION public.set_empresa_context(p_empresa_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM set_config('app.empresa_id', p_empresa_id, true);
  PERFORM set_config('app.current_empresa_id', p_empresa_id, true);
END;
$$;

CREATE OR REPLACE FUNCTION public.set_empresa_context(p_empresa_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public.set_empresa_context(p_empresa_id::text);
END;
$$;

COMMENT ON FUNCTION public.set_empresa_context(text) IS
  'Establece app.empresa_id y app.current_empresa_id para políticas RLS.';

CREATE OR REPLACE FUNCTION public.app_current_empresa_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(
    trim(both from coalesce(
      nullif(current_setting('app.current_empresa_id', true), ''),
      nullif(current_setting('app.empresa_id', true), '')
    )),
    ''
  );
$$;

COMMENT ON FUNCTION public.app_current_empresa_id() IS
  'Tenant activo en la sesión (PostgREST/transacción). Vacío ⇒ políticas no devuelven filas.';

-- Nota: auditoria.empresa_id puede ser NULL; esas filas no serán visibles con esta política.

-- PORTES
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS portes_tenant_all ON public.portes;
    CREATE POLICY portes_tenant_all ON public.portes
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  ELSE
    RAISE NOTICE 'Omitido RLS portes: tabla public.portes no existe';
  END IF;
END $$;

-- FACTURAS (tabla operativa VeriFactu)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'facturas'
  ) THEN
    ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS facturas_tenant_all ON public.facturas;
    CREATE POLICY facturas_tenant_all ON public.facturas
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- GASTOS (puede tener política previa; reemplazar)
ALTER TABLE public.gastos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gastos_por_empresa ON public.gastos;
DROP POLICY IF EXISTS gastos_tenant_all ON public.gastos;
CREATE POLICY gastos_tenant_all ON public.gastos
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- FLOTA
ALTER TABLE public.flota ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS flota_tenant_all ON public.flota;
CREATE POLICY flota_tenant_all ON public.flota
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- AUDITORÍA (filas sin empresa_id no visibles con tenant)
ALTER TABLE public.auditoria ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS auditoria_tenant_all ON public.auditoria;
CREATE POLICY auditoria_tenant_all ON public.auditoria
  FOR ALL
  USING (
    empresa_id IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  )
  WITH CHECK (
    empresa_id IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  );

-- PRESUPUESTOS
ALTER TABLE public.presupuestos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS presupuestos_tenant_all ON public.presupuestos;
CREATE POLICY presupuestos_tenant_all ON public.presupuestos
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- INVENTARIO / EMPLEADOS / ECO (si existen)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'inventario') THEN
    ALTER TABLE public.inventario ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS inventario_tenant_all ON public.inventario;
    CREATE POLICY inventario_tenant_all ON public.inventario FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'empleados') THEN
    ALTER TABLE public.empleados ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS empleados_tenant_all ON public.empleados;
    CREATE POLICY empleados_tenant_all ON public.empleados FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'eco_registros') THEN
    ALTER TABLE public.eco_registros ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS eco_registros_tenant_all ON public.eco_registros;
    CREATE POLICY eco_registros_tenant_all ON public.eco_registros FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- MANTENIMIENTO_FLOTA (si existe y tiene empresa_id)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'mantenimiento_flota' AND column_name = 'empresa_id'
  ) THEN
    ALTER TABLE public.mantenimiento_flota ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS mantenimiento_flota_tenant_all ON public.mantenimiento_flota;
    CREATE POLICY mantenimiento_flota_tenant_all ON public.mantenimiento_flota FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;


-- >>> MIGRATION FILE: 11_20260325_pii_widen_nif_ferrnet_columns.sql.json
-- PII encryption compatibility: Fernet tokens are longer than legacy VARCHAR limits.
-- We widen these columns to `text` so encrypted values can be persisted safely.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'empresas'
      AND column_name = 'nif'
  ) THEN
    ALTER TABLE public.empresas ALTER COLUMN nif TYPE text;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'facturas'
      AND column_name = 'nif_emisor'
  ) THEN
    ALTER TABLE public.facturas ALTER COLUMN nif_emisor TYPE text;
  END IF;
END $$;



-- >>> MIGRATION FILE: 12_20260325_rls_granular_profiles_empresa_id_lock.sql.json
-- =============================================================================
-- Auditoría seguridad: políticas RLS explícitas (SELECT/INSERT/UPDATE/DELETE)
-- para portes, vehículos/flota y auditoría; bloqueo de cambio de empresa_id en profiles.
-- =============================================================================
-- Requisitos: Supabase (auth.jwt(), auth.uid(), auth.role()).
-- Contexto tenant: public.app_current_empresa_id()::text (ver migración 20260324).
-- =============================================================================

-- ─── PORTES: cuatro políticas explícitas ───────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS portes_tenant_all ON public.portes;
    DROP POLICY IF EXISTS portes_select_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_insert_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_update_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_delete_tenant ON public.portes;

    CREATE POLICY portes_select_tenant ON public.portes
      FOR SELECT
      USING (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY portes_insert_tenant ON public.portes
      FOR INSERT
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY portes_update_tenant ON public.portes
      FOR UPDATE
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY portes_delete_tenant ON public.portes
      FOR DELETE
      USING (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- ─── VEHÍCULOS: tabla public.vehiculos (si existe) ─────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    ALTER TABLE public.vehiculos ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS vehiculos_tenant_all ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_select_tenant ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_insert_tenant ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_update_tenant ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_delete_tenant ON public.vehiculos;

    CREATE POLICY vehiculos_select_tenant ON public.vehiculos
      FOR SELECT
      USING (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY vehiculos_insert_tenant ON public.vehiculos
      FOR INSERT
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY vehiculos_update_tenant ON public.vehiculos
      FOR UPDATE
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY vehiculos_delete_tenant ON public.vehiculos
      FOR DELETE
      USING (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- ─── FLOTA (sinónimo operativo de “vehículos” en este proyecto) ────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'flota'
  ) THEN
    ALTER TABLE public.flota ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS flota_tenant_all ON public.flota;
    DROP POLICY IF EXISTS flota_select_tenant ON public.flota;
    DROP POLICY IF EXISTS flota_insert_tenant ON public.flota;
    DROP POLICY IF EXISTS flota_update_tenant ON public.flota;
    DROP POLICY IF EXISTS flota_delete_tenant ON public.flota;

    CREATE POLICY flota_select_tenant ON public.flota
      FOR SELECT
      USING (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY flota_insert_tenant ON public.flota
      FOR INSERT
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY flota_update_tenant ON public.flota
      FOR UPDATE
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY flota_delete_tenant ON public.flota
      FOR DELETE
      USING (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- ─── AUDITORÍA: cuatro políticas (requiere empresa_id NOT NULL) ───────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'auditoria'
  ) THEN
    ALTER TABLE public.auditoria ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS auditoria_tenant_all ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_select_tenant ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_insert_tenant ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_update_tenant ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_delete_tenant ON public.auditoria;

    CREATE POLICY auditoria_select_tenant ON public.auditoria
      FOR SELECT
      USING (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );

    CREATE POLICY auditoria_insert_tenant ON public.auditoria
      FOR INSERT
      WITH CHECK (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );

    CREATE POLICY auditoria_update_tenant ON public.auditoria
      FOR UPDATE
      USING (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      )
      WITH CHECK (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );

    CREATE POLICY auditoria_delete_tenant ON public.auditoria
      FOR DELETE
      USING (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );
  END IF;
END $$;

-- ─── PROFILES: inmutabilidad de empresa_id salvo service_role / superadmin ─
-- Supabase: sesiones `authenticated` no pueden reasignar tenant.
-- service_role (backend con clave service) bypass RLS pero el trigger sigue siendo
-- útil si se escribe con un rol que no bypass; para DEFINER clarity usamos auth.role().

CREATE OR REPLACE FUNCTION public.profiles_block_empresa_id_escalation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  jwt jsonb;
  is_superadmin boolean;
BEGIN
  IF TG_OP <> 'UPDATE' THEN
    RETURN NEW;
  END IF;

  IF NEW.empresa_id IS NOT DISTINCT FROM OLD.empresa_id THEN
    RETURN NEW;
  END IF;

  -- Rol de conexión Postgres (PostgREST / pooler)
  IF current_setting('role', true) = 'service_role' THEN
    RETURN NEW;
  END IF;

  -- Superadmin vía JWT (configurar en Supabase Auth → User → app_metadata)
  BEGIN
    jwt := auth.jwt();
  EXCEPTION WHEN OTHERS THEN
    jwt := NULL;
  END;

  is_superadmin := coalesce((jwt -> 'app_metadata' ->> 'is_superadmin')::boolean, false)
    OR lower(coalesce(jwt -> 'app_metadata' ->> 'role', '')) = 'superadmin';

  IF is_superadmin THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION
    'SECURITY: empresa_id en profiles no es editable para este rol. Use service_role o app_metadata.is_superadmin.';
END;
$$;

COMMENT ON FUNCTION public.profiles_block_empresa_id_escalation() IS
  'Impide cambiar profiles.empresa_id salvo service_role o JWT app_metadata.is_superadmin / role=superadmin.';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    DROP TRIGGER IF EXISTS trg_profiles_block_empresa_id ON public.profiles;
    CREATE TRIGGER trg_profiles_block_empresa_id
      BEFORE UPDATE ON public.profiles
      FOR EACH ROW
      EXECUTE PROCEDURE public.profiles_block_empresa_id_escalation();

    -- Políticas mínimas recomendadas (ajusta según tu modelo de signup)
    ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS profiles_select_authenticated ON public.profiles;
    CREATE POLICY profiles_select_authenticated ON public.profiles
      FOR SELECT
      TO authenticated
      USING (auth.uid() = id);

    DROP POLICY IF EXISTS profiles_update_authenticated ON public.profiles;
    CREATE POLICY profiles_update_authenticated ON public.profiles
      FOR UPDATE
      TO authenticated
      USING (auth.uid() = id)
      WITH CHECK (auth.uid() = id);
  ELSE
    RAISE NOTICE 'Tabla public.profiles no existe: omitido trigger RLS profiles';
  END IF;
END $$;


-- >>> MIGRATION FILE: 13_20260326_add_gocardless_to_profiles.sql.json
-- Persistencia GoCardless para pagos automatizados (mandato SEPA / customer linking).
-- Campos críticos para el flujo de cobro automático del portal cliente.

-- 1) Profiles: referencia estable al customer remoto de GoCardless.
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS gocardless_customer_id text;

COMMENT ON COLUMN public.profiles.gocardless_customer_id IS
  'ID de customer en GoCardless (critical payment identity for automated collections).';

-- Índice único para búsquedas rápidas y evitar colisiones de customer remoto.
CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_gocardless_customer_id
  ON public.profiles (gocardless_customer_id)
  WHERE gocardless_customer_id IS NOT NULL;

-- 2) Clientes: estado de mandato activo para UX/flujo de cobro.
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS mandato_activo boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.clientes.mandato_activo IS
  'TRUE cuando existe mandato SEPA activo para cobro automático vía GoCardless.';

-- 3) set_rbac_session: no requiere cambios funcionales para estos campos.
-- Ambos campos se leen/escriben dentro de filas ya protegidas por las políticas RLS
-- vigentes de profiles/clientes en base a app_current_empresa_id() y app_current_cliente_id().
COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid, uuid) IS
  'Fija app.rbac_role, app.assigned_vehiculo_id, app.current_profile_id y app.cliente_id (portal). Compatible con campos GoCardless de profiles/clientes.';



-- >>> MIGRATION FILE: 14_20260326_flota_vencimientos_alertas.sql.json
-- Vencimientos ITV / seguro para alertas de flota [cite: 2026-03-22]
-- km_proximo_servicio ya existe en esquema legacy (supabase_schema.sql).

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS itv_vencimiento date;

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS seguro_vencimiento date;

COMMENT ON COLUMN public.flota.itv_vencimiento IS 'Próxima ITV (fecha límite)';
COMMENT ON COLUMN public.flota.seguro_vencimiento IS 'Vencimiento póliza seguro';


-- >>> MIGRATION FILE: 15_20260326_master_soft_delete_clientes_empresas.sql.json
-- D2/D3: columnas de borrado lógico en maestras (idempotente).
-- Ejecutar en Supabase si las tablas aún no tienen `deleted_at`.

ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

COMMENT ON COLUMN public.clientes.deleted_at IS 'NULL = activo; IS NOT NULL = archivado (UI oculta)';
COMMENT ON COLUMN public.empresas.deleted_at IS 'NULL = activo; IS NOT NULL = empresa archivada (admin)';


-- >>> MIGRATION FILE: 16_20260327_portes_co2_emitido_esg.sql.json
-- Huella CO2 por porte (motor ESG Enterprise): kg CO2 estimados (distancia × toneladas × factor).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS co2_emitido numeric;

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS peso_ton numeric;

COMMENT ON COLUMN public.portes.co2_emitido IS
  'kg CO2 estimados (Enterprise): distancia_km × peso_ton × factor_emision; ver eco_service.calcular_huella_porte';

COMMENT ON COLUMN public.portes.peso_ton IS
  'Toneladas de carga (opcional API); si NULL, se estima desde bultos al calcular huella.';


-- >>> MIGRATION FILE: 17_20260328_empresas_stripe_billing.sql.json
-- Stripe Billing: cliente, suscripción y límites explícitos por empresa.
ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS plan_type text;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS limite_vehiculos integer;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS stripe_customer_id text;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS stripe_subscription_id text;

COMMENT ON COLUMN public.empresas.plan_type IS
  'Plan SaaS (starter|pro|enterprise|free); alineado con Stripe; si NULL se usa plan';
COMMENT ON COLUMN public.empresas.limite_vehiculos IS
  'Tope de vehículos; NULL = ilimitado (Enterprise)';
COMMENT ON COLUMN public.empresas.stripe_customer_id IS 'cus_… (Stripe Customer)';
COMMENT ON COLUMN public.empresas.stripe_subscription_id IS 'sub_… (Stripe Subscription)';

UPDATE public.empresas
SET plan_type = COALESCE(plan_type, plan)
WHERE plan_type IS NULL AND plan IS NOT NULL;


-- >>> MIGRATION FILE: 18_20260330_facturas_xml_verifactu.sql.json
-- XML de alta VeriFactu (registro exportable / trazabilidad) persistido con la factura.
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS xml_verifactu TEXT;

COMMENT ON COLUMN public.facturas.xml_verifactu IS
  'XML UTF-8 de registro VeriFactu (Cabecera, RegistroFactura, Desglose) generado al sellar el hash';


-- >>> MIGRATION FILE: 19_20260401_esg_flota_porte_vehiculo.sql.json
-- ESG: factor de emisión por vehículo (kg CO₂ / (t·km)) y asignación opcional de porte → flota.
ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS factor_emision_co2_tkm NUMERIC(14, 8);

COMMENT ON COLUMN public.flota.factor_emision_co2_tkm IS
  'Opcional: factor kg CO₂eq por tonelada·km; si NULL se deriva de tipo_motor en la API.';

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS vehiculo_id UUID REFERENCES public.flota (id);

CREATE INDEX IF NOT EXISTS idx_portes_vehiculo_id
  ON public.portes (vehiculo_id)
  WHERE vehiculo_id IS NOT NULL;

COMMENT ON COLUMN public.portes.vehiculo_id IS
  'Vehículo asignado al porte (ESG); NULL = factor global empresa.';


-- >>> MIGRATION FILE: 20_20260403_infra_health_logs.sql.json
-- Logs proactivos de salud (latencia DB, peticiones lentas). Sin credenciales en `message`.
CREATE TABLE IF NOT EXISTS public.infra_health_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  status text NOT NULL,
  latency_ms double precision,
  message text,
  path text,
  method text
);

CREATE INDEX IF NOT EXISTS infra_health_logs_created_at_idx
  ON public.infra_health_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS infra_health_logs_source_idx
  ON public.infra_health_logs (source);

COMMENT ON TABLE public.infra_health_logs IS
  'SRE: salud DB y latencia API; los mensajes deben estar sanitizados (sin URI con contraseña).';


-- >>> MIGRATION FILE: 21_20260404_portes_activos_math_engine_view.sql.json
-- Vista operativa para mapa de flota:
-- - Portes activos (pendientes) con asignación de vehículo.
-- - Margen estimado por porte basado en la métrica del Math Engine (margen EBITDA/km histórico).
-- - Coordenadas y matrícula para consumo directo por API `/flota/estado-actual`.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS lat double precision,
  ADD COLUMN IF NOT EXISTS lng double precision;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    EXECUTE '
      ALTER TABLE public.vehiculos
        ADD COLUMN IF NOT EXISTS lat double precision,
        ADD COLUMN IF NOT EXISTS lng double precision
    ';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_portes_activos_lookup
  ON public.portes (empresa_id, estado, vehiculo_id)
  WHERE deleted_at IS NULL;

DO $$
DECLARE
  vehiculos_exists boolean;
  sql_text text;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) INTO vehiculos_exists;

  sql_text := '
    CREATE OR REPLACE VIEW public.portes_activos AS
    WITH ingresos AS (
      SELECT
        f.empresa_id,
        SUM(
          CASE
            WHEN f.base_imponible IS NOT NULL THEN COALESCE(f.base_imponible, 0)::double precision
            ELSE GREATEST(COALESCE(f.total_factura, 0)::double precision - COALESCE(f.cuota_iva, 0)::double precision, 0)
          END
        ) AS ingresos_netos_sin_iva,
        SUM(COALESCE(f.total_km_estimados_snapshot, 0)::double precision) AS km_facturados
      FROM public.facturas f
      GROUP BY f.empresa_id
    ),
    gastos AS (
      SELECT
        g.empresa_id,
        SUM(
          GREATEST(
            COALESCE(g.total_eur, g.total_chf, 0)::double precision
            - CASE
                WHEN COALESCE(g.iva, 0)::double precision > 0 THEN COALESCE(g.iva, 0)::double precision
                ELSE 0
              END,
            0
          )
        ) AS gastos_netos_sin_iva
      FROM public.gastos g
      WHERE g.deleted_at IS NULL
      GROUP BY g.empresa_id
    ),
    margen_empresa AS (
      SELECT
        i.empresa_id,
        CASE
          WHEN COALESCE(i.km_facturados, 0) > 0
            THEN (COALESCE(i.ingresos_netos_sin_iva, 0) - COALESCE(ga.gastos_netos_sin_iva, 0)) / i.km_facturados
          ELSE 0
        END AS margen_km_eur
      FROM ingresos i
      LEFT JOIN gastos ga ON ga.empresa_id = i.empresa_id
    )
    SELECT
      p.id,
      p.empresa_id,
      p.vehiculo_id,
      p.origen,
      p.destino,';

  IF vehiculos_exists THEN
    sql_text := sql_text || '
      COALESCE(vv.matricula, vf.matricula) AS matricula,
      COALESCE(vv.lat, vf.lat) AS lat,
      COALESCE(vv.lng, vf.lng) AS lng,';
  ELSE
    sql_text := sql_text || '
      vf.matricula AS matricula,
      vf.lat AS lat,
      vf.lng AS lng,';
  END IF;

  sql_text := sql_text || '
      COALESCE(me.margen_km_eur, 0)::double precision AS margen_km_eur,
      ROUND(
        (COALESCE(p.km_estimados, 0)::double precision * COALESCE(me.margen_km_eur, 0)::double precision)::numeric,
        2
      )::double precision AS margen_estimado
    FROM public.portes p
    LEFT JOIN public.flota vf
      ON vf.id = p.vehiculo_id
     AND vf.empresa_id = p.empresa_id
     AND vf.deleted_at IS NULL';

  IF vehiculos_exists THEN
    sql_text := sql_text || '
    LEFT JOIN public.vehiculos vv
      ON vv.id = p.vehiculo_id
     AND vv.empresa_id = p.empresa_id
     AND vv.deleted_at IS NULL';
  END IF;

  sql_text := sql_text || '
    LEFT JOIN margen_empresa me
      ON me.empresa_id = p.empresa_id
    WHERE p.estado = ''pendiente''
      AND p.deleted_at IS NULL
      AND p.vehiculo_id IS NOT NULL
  ';

  EXECUTE sql_text;
END $$;

COMMENT ON VIEW public.portes_activos IS
  'Portes pendientes con vehículo asignado, coordenadas operativas y margen_estimado (Math Engine: margen EBITDA/km × km del porte).';

COMMENT ON COLUMN public.portes_activos.margen_km_eur IS
  'Margen operativo medio EUR/km por empresa (ingresos netos sin IVA - gastos netos sin IVA) / km facturados.';

COMMENT ON COLUMN public.portes_activos.margen_estimado IS
  'Margen estimado por porte = km_estimados del porte × margen_km_eur de la empresa.';


-- >>> MIGRATION FILE: 22_20260405_rbac_user_role_profiles_portes_rls.sql.json
-- =============================================================================
-- RBAC empresarial: tipo user_role, perfiles operativos, sesión app.rbac_role
-- y políticas RLS en public.portes (owner/traffic_manager vs driver).
-- Requisitos: public.set_empresa_context (20260324) y conexión PostgREST con
-- el JWT del usuario para que el backend invoque set_empresa_context + set_rbac_session.
-- =============================================================================

DO $$ BEGIN
  CREATE TYPE public.user_role AS ENUM ('owner', 'traffic_manager', 'driver');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS role public.user_role NOT NULL DEFAULT 'owner'::public.user_role;
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS assigned_vehiculo_id UUID REFERENCES public.flota (id) ON DELETE SET NULL;

    COMMENT ON COLUMN public.profiles.role IS
      'Rol RBAC operativo: owner (total), traffic_manager (operativo sin facturación global), driver (solo lectura portes asignados).';
    COMMENT ON COLUMN public.profiles.assigned_vehiculo_id IS
      'Vehículo (flota) asignado al chófer; obligatorio para aislar filas portes vía RLS si role=driver.';

    -- Histórico: conservar privilegios (equivalente a owner operativo hasta reasignación).
    -- Nuevos registros pueden fijar role en la app; DEFAULT owner mantiene compatibilidad Zero-Downtime.
  END IF;
END $$;

-- Variables de sesión (misma transacción que set_empresa_context en la petición API).
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL
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
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid) IS
  'Fija app.rbac_role y app.assigned_vehiculo_id para políticas RLS (invocar tras set_empresa_context).';

CREATE OR REPLACE FUNCTION public.app_rbac_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(trim(both from current_setting('app.rbac_role', true)), ''),
    'owner'
  );
$$;

CREATE OR REPLACE FUNCTION public.app_assigned_vehiculo_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  s text;
BEGIN
  s := NULLIF(trim(both from current_setting('app.assigned_vehiculo_id', true)), '');
  IF s IS NULL OR s = '' THEN
    RETURN NULL;
  END IF;
  RETURN s::uuid;
EXCEPTION
  WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;

-- ─── PORTES: políticas RBAC ────────────────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS portes_select_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_insert_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_update_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_delete_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_select_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_insert_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_update_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_delete_rbac ON public.portes;

    CREATE POLICY portes_select_rbac ON public.portes
      FOR SELECT
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND (
          public.app_rbac_role() IN ('owner', 'traffic_manager')
          OR (
            public.app_rbac_role() = 'driver'
            AND vehiculo_id IS NOT NULL
            AND vehiculo_id = public.app_assigned_vehiculo_id()
            AND public.app_assigned_vehiculo_id() IS NOT NULL
          )
        )
      );

    CREATE POLICY portes_insert_rbac ON public.portes
      FOR INSERT
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY portes_update_rbac ON public.portes
      FOR UPDATE
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY portes_delete_rbac ON public.portes
      FOR DELETE
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;


-- >>> MIGRATION FILE: 23_20260424_audit_logs_triggers.sql.json
-- =============================================================================
-- Audit logs pasivos (triggers) — portes, facturas, gastos
-- Captura INSERT/UPDATE/DELETE sin tocar la API FastAPI.
-- auth.uid() rellena changed_by cuando la mutación llega con JWT de usuario;
-- con service_role suele ser NULL (acción de sistema / backend).
-- =============================================================================

CREATE TYPE public.audit_action AS ENUM ('INSERT', 'UPDATE', 'DELETE');

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL,
  table_name varchar(128) NOT NULL,
  record_id text NOT NULL,
  action public.audit_action NOT NULL,
  old_data jsonb,
  new_data jsonb,
  changed_by uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_empresa_created
  ON public.audit_logs (empresa_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_table_record
  ON public.audit_logs (table_name, record_id);

COMMENT ON TABLE public.audit_logs IS
  'Trazabilidad de cambios en tablas críticas (triggers). record_id en texto para cualquier tipo de PK.';
COMMENT ON COLUMN public.audit_logs.record_id IS
  'Valor textual de la PK de la fila afectada (UUID u otro).';
COMMENT ON COLUMN public.audit_logs.changed_by IS
  'auth.users.id cuando existe contexto JWT; NULL en escrituras con service_role u operaciones de sistema.';

-- ─── Función genérica de auditoría ───────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.audit_row_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid;
  v_old jsonb;
  v_new jsonb;
  v_record_id text;
  v_action public.audit_action;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'INSERT';
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE';
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE';
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := OLD.empresa_id;
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  v_record_id := coalesce(v_new->>'id', v_old->>'id');
  IF v_record_id IS NULL OR length(trim(v_record_id)) = 0 THEN
    v_record_id := gen_random_uuid()::text;
  END IF;

  INSERT INTO public.audit_logs (
    empresa_id,
    table_name,
    record_id,
    action,
    old_data,
    new_data,
    changed_by
  ) VALUES (
    v_empresa,
    TG_TABLE_NAME::varchar(128),
    v_record_id,
    v_action,
    v_old,
    v_new,
    auth.uid()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.audit_row_change() IS
  'Trigger genérico AFTER INSERT/UPDATE/DELETE → public.audit_logs.';

-- ─── Triggers en tablas críticas ─────────────────────────────────────────────

DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes;
CREATE TRIGGER trg_audit_row_portes
  AFTER INSERT OR UPDATE OR DELETE ON public.portes
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas;
CREATE TRIGGER trg_audit_row_facturas
  AFTER INSERT OR UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_row_gastos ON public.gastos;
CREATE TRIGGER trg_audit_row_gastos
  AFTER INSERT OR UPDATE OR DELETE ON public.gastos
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

-- ─── RLS: lectura por tenant (misma sesión que set_empresa_context) ─────────

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
CREATE POLICY audit_logs_select_tenant ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  );

-- Sin política INSERT/UPDATE/DELETE para roles autenticados: solo el trigger (SECURITY DEFINER) escribe.

GRANT SELECT ON public.audit_logs TO authenticated;
GRANT SELECT ON public.audit_logs TO service_role;


-- >>> MIGRATION FILE: 24_20260426_verifactu_fingerprint_finalizacion.sql.json
-- =============================================================================
-- VeriFactu: huella encadenada (fingerprint), QR de cotejo, finalización atómica
-- =============================================================================

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fingerprint text,
  ADD COLUMN IF NOT EXISTS prev_fingerprint text,
  ADD COLUMN IF NOT EXISTS qr_code_url text,
  ADD COLUMN IF NOT EXISTS is_finalized boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.facturas.fingerprint IS
  'SHA-256 hex encadenado (NIF, número, fecha, total + huella anterior o semilla genesis).';
COMMENT ON COLUMN public.facturas.prev_fingerprint IS
  'Huella fingerprint de la factura finalizada inmediatamente anterior (NULL en la primera).';
COMMENT ON COLUMN public.facturas.qr_code_url IS
  'URL de verificación AEAT (TIKE) codificada en el QR.';
COMMENT ON COLUMN public.facturas.is_finalized IS
  'TRUE tras la operación de finalización; bloquea borrado y mutaciones posteriores.';

-- Integridad: misma empresa no puede repetir huella
CREATE UNIQUE INDEX IF NOT EXISTS uq_facturas_empresa_fingerprint
  ON public.facturas (empresa_id, fingerprint)
  WHERE fingerprint IS NOT NULL AND length(trim(fingerprint)) > 0;

-- Datos ya sellados con hash_registro: tratarlos como finalizados para no exigir re-finalizar
UPDATE public.facturas
SET is_finalized = true,
    fingerprint = coalesce(nullif(trim(fingerprint), ''), nullif(trim(hash_registro), ''))
WHERE hash_registro IS NOT NULL
  AND length(trim(hash_registro::text)) > 0
  AND (is_finalized IS NOT TRUE OR fingerprint IS NULL);

-- ─── Inmutabilidad facturas: permite UNA actualización de finalización ─────

CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF current_setting('role', true) = 'service_role' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE' THEN
    -- Transición explícita a finalizada con huella extendida (sin mutar hash_registro fiscal)
    IF OLD.hash_registro IS NOT NULL
       AND length(trim(OLD.hash_registro::text)) > 0
       AND COALESCE(OLD.is_finalized, false) IS FALSE
       AND COALESCE(NEW.is_finalized, false) IS TRUE
       AND NEW.fingerprint IS NOT NULL
       AND length(trim(NEW.fingerprint::text)) > 0
    THEN
      RETURN NEW;
    END IF;

    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    IF COALESCE(OLD.is_finalized, false) IS TRUE THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido para factura finalizada VeriFactu (tabla facturas)';
    END IF;
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_immutable_hash ON public.facturas;
CREATE TRIGGER trg_facturas_immutable_hash
  BEFORE UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.enforce_immutable_facturas();


-- >>> MIGRATION FILE: 25_20260427_aeat_verifactu_envios.sql.json
-- AEAT SIF / VeriFactu: registro de envíos y metadatos en facturas finalizadas.
-- Permite actualizar solo columnas aeat_sif_* en facturas ya finalizadas (trigger).

CREATE TABLE IF NOT EXISTS public.verifactu_envios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  factura_id bigint NOT NULL REFERENCES public.facturas (id) ON DELETE RESTRICT,
  estado text NOT NULL,
  codigo_error text,
  descripcion_error text,
  csv_aeat text,
  http_status int,
  response_snippet text,
  soap_action text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_verifactu_envios_factura_id
  ON public.verifactu_envios (factura_id);

CREATE INDEX IF NOT EXISTS idx_verifactu_envios_empresa_id
  ON public.verifactu_envios (empresa_id);

COMMENT ON TABLE public.verifactu_envios IS
  'Intentos de remisión SIF VeriFactu a la AEAT (por factura).';
COMMENT ON COLUMN public.verifactu_envios.csv_aeat IS
  'Identificador o trazas CSV devueltas por la AEAT cuando aplica.';

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS aeat_client_cert_path text,
  ADD COLUMN IF NOT EXISTS aeat_client_key_path text,
  ADD COLUMN IF NOT EXISTS aeat_client_p12_path text;

COMMENT ON COLUMN public.empresas.aeat_client_cert_path IS
  'Ruta PEM certificado cliente TLS (mutua); alternativa a variables globales AEAT_CLIENT_* .';
COMMENT ON COLUMN public.empresas.aeat_client_key_path IS
  'Ruta PEM clave privada TLS.';
COMMENT ON COLUMN public.empresas.aeat_client_p12_path IS
  'Ruta bundle PKCS#12 (.p12); contraseña vía AEAT_CLIENT_P12_PASSWORD en el servidor.';

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS aeat_sif_estado text,
  ADD COLUMN IF NOT EXISTS aeat_sif_csv text,
  ADD COLUMN IF NOT EXISTS aeat_sif_codigo text,
  ADD COLUMN IF NOT EXISTS aeat_sif_descripcion text,
  ADD COLUMN IF NOT EXISTS aeat_sif_actualizado_en timestamptz;

COMMENT ON COLUMN public.facturas.aeat_sif_estado IS
  'Estado remisión SIF: aceptado, aceptado_con_errores, rechazado, error_tecnico, pendiente, omitido.';

-- ─── Trigger inmutabilidad: permitir actualizar solo columnas AEAT ─────────

CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  new_j jsonb;
  old_j jsonb;
BEGIN
  IF current_setting('role', true) = 'service_role' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE' THEN
    IF OLD.hash_registro IS NOT NULL
       AND length(trim(OLD.hash_registro::text)) > 0
       AND COALESCE(OLD.is_finalized, false) IS FALSE
       AND COALESCE(NEW.is_finalized, false) IS TRUE
       AND NEW.fingerprint IS NOT NULL
       AND length(trim(NEW.fingerprint::text)) > 0
    THEN
      RETURN NEW;
    END IF;

    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      IF COALESCE(OLD.is_finalized, false) IS TRUE
         AND COALESCE(NEW.is_finalized, false) IS TRUE
      THEN
        new_j := row_to_json(NEW)::jsonb;
        old_j := row_to_json(OLD)::jsonb;
        new_j := new_j
          - 'aeat_sif_estado' - 'aeat_sif_csv' - 'aeat_sif_codigo'
          - 'aeat_sif_descripcion' - 'aeat_sif_actualizado_en';
        old_j := old_j
          - 'aeat_sif_estado' - 'aeat_sif_csv' - 'aeat_sif_codigo'
          - 'aeat_sif_descripcion' - 'aeat_sif_actualizado_en';
        IF new_j IS NOT DISTINCT FROM old_j THEN
          RETURN NEW;
        END IF;
      END IF;
      RAISE EXCEPTION
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    IF COALESCE(OLD.is_finalized, false) IS TRUE THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido para factura finalizada VeriFactu (tabla facturas)';
    END IF;
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

-- Fix typo if any: I introduced _IF_label by mistake - need to remove

-- >>> MIGRATION FILE: 26_20260429_vehiculos_gps_ultima.sql.json
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


-- >>> MIGRATION FILE: 27_20260431_treasury_vencimientos.sql.json
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


-- >>> MIGRATION FILE: 28_20260432_portes_cmr_conductor.sql.json
-- CMR: nombre del conductor (opcional; si NULL, el PDF deja la casilla en blanco).
ALTER TABLE public.portes ADD COLUMN IF NOT EXISTS conductor_nombre text;

COMMENT ON COLUMN public.portes.conductor_nombre IS
  'Nombre del conductor para carta de porte (CMR); opcional.';


-- >>> MIGRATION FILE: 29_20260433_clientes_cuenta_contable.sql.json
-- Cuenta contable PGC opcional por cliente (exportación a gestoría).
ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS cuenta_contable text;

COMMENT ON COLUMN public.clientes.cuenta_contable IS
  'Cuenta 430… si se informa; si NULL, la exportación genera 430 + sufijo determinista desde id.';


-- >>> MIGRATION FILE: 30_20260434_portes_firma_entrega_pod.sql.json
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


-- >>> MIGRATION FILE: 31_20260435_fix_rls_leaks.sql.json
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


-- >>> MIGRATION FILE: 32_20260437_esg_auditoria_fuel_import.sql.json
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



-- >>> MIGRATION FILE: 33_20260438_audit_logs_append_only_security.sql.json
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



-- >>> MIGRATION FILE: 34_20260439_audit_logs_select_strict_admin.sql.json
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



-- >>> MIGRATION FILE: 35_20260445_portes_dni_consignatario_pod.sql.json
-- DNI/NIE opcional del consignatario (POD).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS dni_consignatario text;

COMMENT ON COLUMN public.portes.dni_consignatario IS 'DNI/NIE del consignatario (opcional, entrega POD).';


-- >>> MIGRATION FILE: 36_20260447_portal_onboarding_risk_acceptance.sql.json
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



-- >>> MIGRATION FILE: 37_20260501_add_portes_co2_kg.sql.json
-- Campo de emisiones simplificado para reportes financieros ESG.
alter table if exists public.portes
add column if not exists co2_kg numeric;

-- Backfill inicial desde campo legacy si existe valor.
update public.portes
set co2_kg = coalesce(co2_kg, co2_emitido)
where co2_kg is null;


-- >>> MIGRATION FILE: 38_20260502_facturas_fingerprint_hash_chain.sql.json
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


-- >>> MIGRATION FILE: 39_audit_rls_status.sql.json
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
