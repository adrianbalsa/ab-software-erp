-- >>> 04_20260322_auditoria_api_columns_facturas_immutability.sql.json
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


-- >>> 05_20260322_refresh_tokens.sql.json
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


-- >>> 06_20260323_facturas_rectificativas_r1.sql.json
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


-- >>> 07_20260323_rename_columns_legacy_to_api.sql.json
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


-- >>> 08_20260324_esg_certificacion_vw_emissions.sql.json
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


-- >>> 09_20260324_refresh_tokens_ip_user_agent.sql.json
-- Metadatos de sesión (IP + User-Agent) [cite: 2026-03-22]
ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS ip_address TEXT;

ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS user_agent TEXT;

COMMENT ON COLUMN public.refresh_tokens.ip_address IS 'IP del cliente al crear/rotar la sesión (mejor esfuerzo; detrás de proxy usar X-Forwarded-For).';
COMMENT ON COLUMN public.refresh_tokens.user_agent IS 'Cabecera User-Agent en login/refresh.';


-- >>> 10_20260324_rls_tenant_current_empresa.sql.json
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


-- >>> 11_20260325_pii_widen_nif_ferrnet_columns.sql.json
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



-- >>> 12_20260325_rls_granular_profiles_empresa_id_lock.sql.json
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
