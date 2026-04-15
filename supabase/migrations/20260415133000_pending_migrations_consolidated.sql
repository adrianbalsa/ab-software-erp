-- Consolidated pending migrations for manual execution in Supabase SQL Editor
-- Generated automatically because `supabase db push` timed out during login role initialization.
-- Total pending files: 71

-- ============================================================================
-- [1/71] BEGIN FILE: 20260319000000_fiscal_immutability_soft_delete_snapshot.sql
-- ============================================================================

-- =============================================================================
-- Fase persistencia fiscal (2026-03-19)
-- - Inmutabilidad: facturas + auditoria con hash_registro → sin UPDATE/DELETE
--   (excepción: rol Postgres service_role para compensaciones / mantenimiento).
-- - Borrado lógico: deleted_at en portes, gastos, flota, vehiculos (si existe).
-- - Facturas: snapshot JSON de líneas de porte + total km (motor matemático).
-- - Auditoría: columna opcional hash_registro para mismas reglas de inmutabilidad.
-- =============================================================================

-- ─── Columnas factura (snapshot portes al emitir) ───────────────────────────
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS porte_lineas_snapshot jsonb;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS total_km_estimados_snapshot double precision;

COMMENT ON COLUMN public.facturas.porte_lineas_snapshot IS
  'Líneas congeladas al emitir: porte_id, precio_pactado, km_estimados, ruta, etc.';
COMMENT ON COLUMN public.facturas.total_km_estimados_snapshot IS
  'Suma de km_estimados de las líneas facturadas (valor estático fiscal).';

-- ─── Auditoría: hash_registro (inmutabilidad alineada con facturas) ─────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'auditoria'
  ) THEN
    ALTER TABLE public.auditoria
      ADD COLUMN IF NOT EXISTS hash_registro text;
  END IF;
END $$;

-- ─── Soft delete ───────────────────────────────────────────────────────────
ALTER TABLE public.portes ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE public.gastos ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_portes_empresa_not_deleted
  ON public.portes (empresa_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_gastos_empresa_not_deleted
  ON public.gastos (empresa_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_flota_empresa_not_deleted
  ON public.flota (empresa_id) WHERE deleted_at IS NULL;

-- ─── Función inmutabilidad (hash_registro no vacío) ─────────────────────────
CREATE OR REPLACE FUNCTION public.enforce_immutable_when_hashed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- Backend Supabase service_role: permite DELETE/UPDATE (p. ej. rollback compensación).
  IF current_setting('role', true) = 'service_role' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE' THEN
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla %)',
        TG_TABLE_NAME;
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla %)',
        TG_TABLE_NAME;
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.enforce_immutable_when_hashed() IS
  'Bloquea UPDATE/DELETE si hash_registro está fijado; service_role puede mutar.';

-- Facturas
DROP TRIGGER IF EXISTS trg_facturas_immutable_hash ON public.facturas;
CREATE TRIGGER trg_facturas_immutable_hash
  BEFORE UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.enforce_immutable_when_hashed();

-- Auditoría (solo si existe columna hash_registro; creada arriba)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'auditoria' AND column_name = 'hash_registro'
  ) THEN
    DROP TRIGGER IF EXISTS trg_auditoria_immutable_hash ON public.auditoria;
    CREATE TRIGGER trg_auditoria_immutable_hash
      BEFORE UPDATE OR DELETE ON public.auditoria
      FOR EACH ROW
      EXECUTE PROCEDURE public.enforce_immutable_when_hashed();
  END IF;
END $$;


-- ============================================================================
-- [1/71] END FILE: 20260319000000_fiscal_immutability_soft_delete_snapshot.sql
-- ============================================================================

-- ============================================================================
-- [2/71] BEGIN FILE: 20260319000001_gastos_fiscal_verifactu.sql
-- ============================================================================

-- Fase 2: campos fiscales para trazabilidad (VeriFactu / ticket).
-- Ejecutar en Supabase SQL Editor si la tabla `gastos` aún no los tiene.

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS nif_proveedor text;

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS iva numeric;

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS total_eur numeric;

COMMENT ON COLUMN public.gastos.nif_proveedor IS 'NIF/CIF del proveedor (ticket/factura simplificada)';
COMMENT ON COLUMN public.gastos.iva IS 'Cuota de IVA en EUR cuando conste en el documento';
COMMENT ON COLUMN public.gastos.total_eur IS 'Importe total del gasto en EUR (referencia para reporting y cumplimiento)';


-- ============================================================================
-- [2/71] END FILE: 20260319000001_gastos_fiscal_verifactu.sql
-- ============================================================================

-- ============================================================================
-- [3/71] BEGIN FILE: 20260319000002_facturas_verifactu_f1.sql
-- ============================================================================

-- Campos VeriFactu / SIF para tabla facturas (ejecutar en Supabase si aún no existen).

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS tipo_factura text;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS num_factura text;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS nif_emisor text;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS hash_registro text;

COMMENT ON COLUMN public.facturas.tipo_factura IS 'p.ej. F1 factura completa (VeriFactu)';
COMMENT ON COLUMN public.facturas.num_factura IS 'Serie-Año-Secuencial';
COMMENT ON COLUMN public.facturas.nif_emisor IS 'NIF obligado tributario (empresa)';
COMMENT ON COLUMN public.facturas.hash_registro IS 'SHA-256 huella de registro (encadenamiento)';


-- ============================================================================
-- [3/71] END FILE: 20260319000002_facturas_verifactu_f1.sql
-- ============================================================================

-- ============================================================================
-- [4/71] BEGIN FILE: 20260319000003_auditoria_api_columns_facturas_immutability.sql
-- ============================================================================

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


-- ============================================================================
-- [4/71] END FILE: 20260319000003_auditoria_api_columns_facturas_immutability.sql
-- ============================================================================

-- ============================================================================
-- [5/71] BEGIN FILE: 20260319000004_refresh_tokens.sql
-- ============================================================================

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


-- ============================================================================
-- [5/71] END FILE: 20260319000004_refresh_tokens.sql
-- ============================================================================

-- ============================================================================
-- [6/71] BEGIN FILE: 20260319000005_facturas_rectificativas_r1.sql
-- ============================================================================

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


-- ============================================================================
-- [6/71] END FILE: 20260319000005_facturas_rectificativas_r1.sql
-- ============================================================================

-- ============================================================================
-- [7/71] BEGIN FILE: 20260319000006_rename_columns_legacy_to_api.sql
-- ============================================================================

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


-- ============================================================================
-- [7/71] END FILE: 20260319000006_rename_columns_legacy_to_api.sql
-- ============================================================================

-- ============================================================================
-- [8/71] BEGIN FILE: 20260319000007_esg_certificacion_vw_emissions.sql
-- ============================================================================

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


-- ============================================================================
-- [8/71] END FILE: 20260319000007_esg_certificacion_vw_emissions.sql
-- ============================================================================

-- ============================================================================
-- [9/71] BEGIN FILE: 20260319000008_refresh_tokens_ip_user_agent.sql
-- ============================================================================

-- Metadatos de sesión (IP + User-Agent) [cite: 2026-03-22]
ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS ip_address TEXT;

ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS user_agent TEXT;

COMMENT ON COLUMN public.refresh_tokens.ip_address IS 'IP del cliente al crear/rotar la sesión (mejor esfuerzo; detrás de proxy usar X-Forwarded-For).';
COMMENT ON COLUMN public.refresh_tokens.user_agent IS 'Cabecera User-Agent en login/refresh.';


-- ============================================================================
-- [9/71] END FILE: 20260319000008_refresh_tokens_ip_user_agent.sql
-- ============================================================================

-- ============================================================================
-- [10/71] BEGIN FILE: 20260319000009_rls_tenant_current_empresa.sql
-- ============================================================================

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


-- ============================================================================
-- [10/71] END FILE: 20260319000009_rls_tenant_current_empresa.sql
-- ============================================================================

-- ============================================================================
-- [11/71] BEGIN FILE: 20260319000010_pii_widen_nif_ferrnet_columns.sql
-- ============================================================================

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



-- ============================================================================
-- [11/71] END FILE: 20260319000010_pii_widen_nif_ferrnet_columns.sql
-- ============================================================================

-- ============================================================================
-- [12/71] BEGIN FILE: 20260319000011_rls_granular_profiles_empresa_id_lock.sql
-- ============================================================================

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


-- ============================================================================
-- [12/71] END FILE: 20260319000011_rls_granular_profiles_empresa_id_lock.sql
-- ============================================================================

-- ============================================================================
-- [13/71] BEGIN FILE: 20260319000012_add_gocardless_to_profiles.sql
-- ============================================================================

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



-- ============================================================================
-- [13/71] END FILE: 20260319000012_add_gocardless_to_profiles.sql
-- ============================================================================

-- ============================================================================
-- [14/71] BEGIN FILE: 20260319000013_flota_vencimientos_alertas.sql
-- ============================================================================

-- Vencimientos ITV / seguro para alertas de flota [cite: 2026-03-22]
-- km_proximo_servicio ya existe en esquema legacy (supabase_schema.sql).

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS itv_vencimiento date;

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS seguro_vencimiento date;

COMMENT ON COLUMN public.flota.itv_vencimiento IS 'Próxima ITV (fecha límite)';
COMMENT ON COLUMN public.flota.seguro_vencimiento IS 'Vencimiento póliza seguro';


-- ============================================================================
-- [14/71] END FILE: 20260319000013_flota_vencimientos_alertas.sql
-- ============================================================================

-- ============================================================================
-- [15/71] BEGIN FILE: 20260319000014_master_soft_delete_clientes_empresas.sql
-- ============================================================================

-- D2/D3: columnas de borrado lógico en maestras (idempotente).
-- Ejecutar en Supabase si las tablas aún no tienen `deleted_at`.

ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

COMMENT ON COLUMN public.clientes.deleted_at IS 'NULL = activo; IS NOT NULL = archivado (UI oculta)';
COMMENT ON COLUMN public.empresas.deleted_at IS 'NULL = activo; IS NOT NULL = empresa archivada (admin)';


-- ============================================================================
-- [15/71] END FILE: 20260319000014_master_soft_delete_clientes_empresas.sql
-- ============================================================================

-- ============================================================================
-- [16/71] BEGIN FILE: 20260319000015_bank_sync_gocardless.sql
-- ============================================================================

-- GoCardless Bank Account Data: vínculo por empresa (tokens cifrados en aplicación).
-- Columnas de cobro en facturas para conciliación automática.

CREATE TABLE IF NOT EXISTS public.empresa_banco_sync (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  requisition_id_enc TEXT NOT NULL,
  access_token_enc TEXT,
  institution_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT empresa_banco_sync_empresa_unique UNIQUE (empresa_id)
);

COMMENT ON TABLE public.empresa_banco_sync IS
  'GoCardless (Nordigen): requisition_id y access JWT cifrados por la API antes de persistir.';
COMMENT ON COLUMN public.empresa_banco_sync.requisition_id_enc IS 'Fernet ciphertext (base64) del requisition UUID';
COMMENT ON COLUMN public.empresa_banco_sync.access_token_enc IS 'Fernet ciphertext del último access JWT de Bank Account Data';

CREATE INDEX IF NOT EXISTS idx_empresa_banco_sync_empresa ON public.empresa_banco_sync (empresa_id);

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS estado_cobro TEXT NOT NULL DEFAULT 'emitida',
  ADD COLUMN IF NOT EXISTS pago_id TEXT;

COMMENT ON COLUMN public.facturas.estado_cobro IS 'emitida | cobrada';
COMMENT ON COLUMN public.facturas.pago_id IS 'ID movimiento bancario (GoCardless transactionId u otro ref.)';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'empresa_banco_sync'
  ) THEN
    ALTER TABLE public.empresa_banco_sync ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS empresa_banco_sync_tenant_all ON public.empresa_banco_sync;
    CREATE POLICY empresa_banco_sync_tenant_all ON public.empresa_banco_sync
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;


-- ============================================================================
-- [16/71] END FILE: 20260319000015_bank_sync_gocardless.sql
-- ============================================================================

-- ============================================================================
-- [17/71] BEGIN FILE: 20260319000016_normativa_euro_flota_vehiculos.sql
-- ============================================================================

-- Normativa EURO explícita para factores CO₂ por vehículo (ESG engine).
-- Complementa certificacion_emisiones (auditoría / legacy) sin sustituirla.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS normativa_euro text NOT NULL DEFAULT 'Euro VI';

ALTER TABLE public.vehiculos
  ADD COLUMN IF NOT EXISTS normativa_euro text NOT NULL DEFAULT 'Euro VI';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'flota_normativa_euro_check'
  ) THEN
    ALTER TABLE public.flota
      ADD CONSTRAINT flota_normativa_euro_check
      CHECK (normativa_euro IN ('Euro IV', 'Euro V', 'Euro VI'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'vehiculos_normativa_euro_check'
  ) THEN
    ALTER TABLE public.vehiculos
      ADD CONSTRAINT vehiculos_normativa_euro_check
      CHECK (normativa_euro IN ('Euro IV', 'Euro V', 'Euro VI'));
  END IF;
END $$;

COMMENT ON COLUMN public.flota.normativa_euro IS
  'Norma EURO para factor kg CO2/km (ESG). Sincronizada conceptualmente con certificacion_emisiones cuando aplica.';

COMMENT ON COLUMN public.vehiculos.normativa_euro IS
  'Norma EURO para factor kg CO2/km (ESG).';

-- Backfill conservador desde certificación histórica (Euro IV no existía en el check antiguo → Euro VI salvo Euro V/VI).
UPDATE public.flota
SET normativa_euro = CASE trim(coalesce(certificacion_emisiones, ''))
  WHEN 'Euro V' THEN 'Euro V'
  WHEN 'Euro VI' THEN 'Euro VI'
  ELSE 'Euro VI'
END
WHERE normativa_euro = 'Euro VI';

UPDATE public.vehiculos
SET normativa_euro = CASE trim(coalesce(certificacion_emisiones, ''))
  WHEN 'Euro V' THEN 'Euro V'
  WHEN 'Euro VI' THEN 'Euro VI'
  ELSE 'Euro VI'
END
WHERE normativa_euro = 'Euro VI';


-- ============================================================================
-- [17/71] END FILE: 20260319000016_normativa_euro_flota_vehiculos.sql
-- ============================================================================

-- ============================================================================
-- [18/71] BEGIN FILE: 20260319000017_portes_co2_emitido_esg.sql
-- ============================================================================

-- Huella CO2 por porte (motor ESG Enterprise): kg CO2 estimados (distancia × toneladas × factor).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS co2_emitido numeric;

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS peso_ton numeric;

COMMENT ON COLUMN public.portes.co2_emitido IS
  'kg CO2 estimados (Enterprise): distancia_km × peso_ton × factor_emision; ver eco_service.calcular_huella_porte';

COMMENT ON COLUMN public.portes.peso_ton IS
  'Toneladas de carga (opcional API); si NULL, se estima desde bultos al calcular huella.';


-- ============================================================================
-- [18/71] END FILE: 20260319000017_portes_co2_emitido_esg.sql
-- ============================================================================

-- ============================================================================
-- [19/71] BEGIN FILE: 20260319000018_webhooks_hmac_endpoints_developer.sql
-- ============================================================================

-- Webhooks: columnas explícitas (secret_key, event_types, is_active), índice parcial,
-- rol developer (integraciones API) y sesión RBAC alineada.

-- ─── Enum user_role: developer ───
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE n.nspname = 'public' AND t.typname = 'user_role')
     AND NOT EXISTS (
       SELECT 1 FROM pg_enum e
       JOIN pg_type t ON t.oid = e.enumtypid
       JOIN pg_namespace n ON n.oid = t.typnamespace
       WHERE n.nspname = 'public' AND t.typname = 'user_role' AND e.enumlabel = 'developer'
     ) THEN
    ALTER TYPE public.user_role ADD VALUE 'developer';
  END IF;
END $$;

-- ─── webhook_endpoints: renombrar columnas legacy ───
DO $$
BEGIN
  IF to_regclass('public.webhook_endpoints') IS NULL THEN
    RETURN;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'webhook_endpoints' AND column_name = 'secret'
  ) THEN
    ALTER TABLE public.webhook_endpoints RENAME COLUMN secret TO secret_key;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'webhook_endpoints' AND column_name = 'events'
  ) THEN
    ALTER TABLE public.webhook_endpoints RENAME COLUMN events TO event_types;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'webhook_endpoints' AND column_name = 'active'
  ) THEN
    ALTER TABLE public.webhook_endpoints RENAME COLUMN active TO is_active;
  END IF;
END $$;

DROP INDEX IF EXISTS public.idx_webhook_endpoints_empresa_active;
CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_empresa_active
  ON public.webhook_endpoints (empresa_id)
  WHERE is_active = true;

COMMENT ON COLUMN public.webhook_endpoints.secret_key IS 'Secreto HMAC-SHA256 para cabecera X-ABLogistics-Signature.';
COMMENT ON COLUMN public.webhook_endpoints.event_types IS 'Lista de eventos suscritos o * para todos.';
COMMENT ON COLUMN public.webhook_endpoints.is_active IS 'Si false, no se entregan notificaciones.';

-- ─── Sesión RBAC: permitir developer ───
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL,
  p_profile_id uuid DEFAULT NULL,
  p_cliente_id uuid DEFAULT NULL
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
  IF r NOT IN ('owner', 'traffic_manager', 'driver', 'cliente', 'developer') THEN
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
  IF r = 'cliente' AND p_cliente_id IS NOT NULL THEN
    PERFORM set_config('app.cliente_id', p_cliente_id::text, true);
  ELSE
    PERFORM set_config('app.cliente_id', '', true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid, uuid) IS
  'Fija app.rbac_role (owner|traffic_manager|driver|cliente|developer), vehículo, perfil y cliente portal.';


-- ============================================================================
-- [19/71] END FILE: 20260319000018_webhooks_hmac_endpoints_developer.sql
-- ============================================================================

-- ============================================================================
-- [20/71] BEGIN FILE: 20260319000019_empresas_stripe_billing.sql
-- ============================================================================

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


-- ============================================================================
-- [20/71] END FILE: 20260319000019_empresas_stripe_billing.sql
-- ============================================================================

-- ============================================================================
-- [21/71] BEGIN FILE: 20260319000020_user_accounts_mfa.sql
-- ============================================================================

-- Vincular varios proveedores de identidad al mismo usuario (OIDC / password) y campos MFA (TOTP futuro).

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS mfa_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS mfa_secret text;

COMMENT ON COLUMN public.usuarios.mfa_enabled IS 'Si true, el login exigirá segundo factor cuando se implemente TOTP';
COMMENT ON COLUMN public.usuarios.mfa_secret IS 'Secreto TOTP (base32); NULL si MFA no configurado';

CREATE TABLE IF NOT EXISTS public.user_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.usuarios (id) ON DELETE CASCADE,
  provider text NOT NULL,
  provider_subject text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_accounts_provider_subject_unique UNIQUE (provider, provider_subject),
  CONSTRAINT user_accounts_provider_chk CHECK (
    provider = ANY (ARRAY['password'::text, 'google'::text, 'microsoft'::text])
  )
);

CREATE INDEX IF NOT EXISTS idx_user_accounts_user_id ON public.user_accounts (user_id);

COMMENT ON TABLE public.user_accounts IS
  'Identidades externas vinculadas a usuarios.id (mismo usuario, varios métodos de login)';


-- ============================================================================
-- [21/71] END FILE: 20260319000020_user_accounts_mfa.sql
-- ============================================================================

-- ============================================================================
-- [22/71] BEGIN FILE: 20260319000021_facturas_xml_verifactu.sql
-- ============================================================================

-- XML de alta VeriFactu (registro exportable / trazabilidad) persistido con la factura.
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS xml_verifactu TEXT;

COMMENT ON COLUMN public.facturas.xml_verifactu IS
  'XML UTF-8 de registro VeriFactu (Cabecera, RegistroFactura, Desglose) generado al sellar el hash';


-- ============================================================================
-- [22/71] END FILE: 20260319000021_facturas_xml_verifactu.sql
-- ============================================================================

-- ============================================================================
-- [23/71] BEGIN FILE: 20260319000022_esg_and_queues.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS engine_class varchar(32) NOT NULL DEFAULT 'EURO_VI',
  ADD COLUMN IF NOT EXISTS fuel_type varchar(32) NOT NULL DEFAULT 'DIESEL';

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS km_vacio numeric(12,3) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS subcontratado boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS public.webhook_events (
  id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  provider varchar(64) NOT NULL,
  event_type varchar(128) NOT NULL,
  payload jsonb NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  error_log text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_status_created_at
  ON public.webhook_events (status, created_at);

CREATE INDEX IF NOT EXISTS idx_webhook_events_provider_event_type
  ON public.webhook_events (provider, event_type);

COMMIT;


-- ============================================================================
-- [23/71] END FILE: 20260319000022_esg_and_queues.sql
-- ============================================================================

-- ============================================================================
-- [24/71] BEGIN FILE: 20260319000023_esg_dynamic_co2_empty_km.sql
-- ============================================================================

-- ESG phase completion: dynamic factors + empty kilometers metadata.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS engine_class varchar(32) NOT NULL DEFAULT 'EURO_VI',
  ADD COLUMN IF NOT EXISTS fuel_type varchar(32) NOT NULL DEFAULT 'DIESEL';

COMMENT ON COLUMN public.flota.engine_class IS
  'Clase de motor para factores dinámicos ESG (ej. EURO_VI, EURO_V, EURO_IV, EV).';
COMMENT ON COLUMN public.flota.fuel_type IS
  'Tipo de combustible para factores dinámicos ESG (ej. DIESEL, ELECTRIC, HIBRIDO, GASOLINA).';

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS km_vacio numeric(12,3) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS subcontratado boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.portes.km_vacio IS
  'Kilómetros recorridos en vacío (sin carga) para cálculo dinámico de CO2.';
COMMENT ON COLUMN public.portes.subcontratado IS
  'true si el porte se ejecuta por tercero (Scope 3); false para flota propia (Scope 1).';


-- ============================================================================
-- [24/71] END FILE: 20260319000023_esg_dynamic_co2_empty_km.sql
-- ============================================================================

-- ============================================================================
-- [25/71] BEGIN FILE: 20260319000024_facturas_qr_content.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS qr_content text;

COMMENT ON COLUMN public.facturas.qr_content IS
  'URL completa codificada en el QR VeriFactu (incluye hc con 8 chars de huella_hash).';

COMMIT;


-- ============================================================================
-- [25/71] END FILE: 20260319000024_facturas_qr_content.sql
-- ============================================================================

-- ============================================================================
-- [26/71] BEGIN FILE: 20260319000025_finance_snapshots.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.finance_kpi_snapshots (
  id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  empresa_id uuid NOT NULL,
  period_month text NOT NULL CHECK (period_month ~ '^\d{4}-(0[1-9]|1[0-2])$'),
  ingresos_operacion numeric(18,2) NOT NULL DEFAULT 0,
  gastos_operacion numeric(18,2) NOT NULL DEFAULT 0,
  ebitda numeric(18,2) NOT NULL DEFAULT 0,
  last_recalculated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ux_finance_kpi_snapshots_empresa_period UNIQUE (empresa_id, period_month)
);

CREATE INDEX IF NOT EXISTS idx_finance_kpi_snapshots_empresa_month
  ON public.finance_kpi_snapshots (empresa_id, period_month);

CREATE OR REPLACE FUNCTION public.round_half_even(p_value numeric, p_scale int DEFAULT 2)
RETURNS numeric
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  v_factor numeric;
  v_shifted numeric;
  v_abs numeric;
  v_floor numeric;
  v_frac numeric;
  v_rounded numeric;
  v_sign numeric;
BEGIN
  IF p_value IS NULL THEN
    RETURN NULL;
  END IF;
  IF p_scale < 0 THEN
    RAISE EXCEPTION 'p_scale must be >= 0';
  END IF;

  v_factor := power(10::numeric, p_scale);
  v_shifted := p_value * v_factor;
  v_sign := CASE WHEN v_shifted < 0 THEN -1 ELSE 1 END;
  v_abs := abs(v_shifted);
  v_floor := trunc(v_abs);
  v_frac := v_abs - v_floor;

  IF v_frac > 0.5 THEN
    v_rounded := v_floor + 1;
  ELSIF v_frac < 0.5 THEN
    v_rounded := v_floor;
  ELSE
    IF mod(v_floor::numeric, 2) = 0 THEN
      v_rounded := v_floor;
    ELSE
      v_rounded := v_floor + 1;
    END IF;
  END IF;

  RETURN (v_rounded * v_sign) / v_factor;
END;
$$;

CREATE OR REPLACE FUNCTION public._upsert_monthly_kpis(
  p_empresa_id uuid,
  p_period_month text
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_ingresos numeric(18,2);
  v_gastos numeric(18,2);
  v_ebitda numeric(18,2);
BEGIN
  IF p_empresa_id IS NULL OR p_period_month IS NULL OR p_period_month !~ '^\d{4}-(0[1-9]|1[0-2])$' THEN
    RETURN;
  END IF;

  SELECT
    COALESCE(sum(
      public.round_half_even(
        CASE
          WHEN f.base_imponible IS NOT NULL THEN f.base_imponible
          ELSE GREATEST(COALESCE(f.total_factura, 0) - COALESCE(f.cuota_iva, 0), 0)
        END,
        2
      )
    ), 0)::numeric(18,2)
  INTO v_ingresos
  FROM public.facturas f
  WHERE f.empresa_id = p_empresa_id
    AND to_char(COALESCE(f.fecha_emision, f.fecha::date, f.fecha_factura::date), 'YYYY-MM') = p_period_month
    AND lower(trim(COALESCE(f.estado_cobro, ''))) = 'cobrada'
    AND f.deleted_at IS NULL;

  SELECT
    COALESCE(sum(
      public.round_half_even(
        GREATEST(
          COALESCE(COALESCE(g.total_eur, g.total_chf), 0) -
          CASE
            WHEN g.iva IS NULL OR g.iva <= 0 THEN 0
            ELSE g.iva
          END,
          0
        ),
        2
      )
    ), 0)::numeric(18,2)
  INTO v_gastos
  FROM public.gastos g
  WHERE g.empresa_id = p_empresa_id
    AND to_char(g.fecha::date, 'YYYY-MM') = p_period_month
    AND g.deleted_at IS NULL;

  v_ebitda := public.round_half_even(v_ingresos - v_gastos, 2)::numeric(18,2);

  INSERT INTO public.finance_kpi_snapshots (
    empresa_id,
    period_month,
    ingresos_operacion,
    gastos_operacion,
    ebitda,
    last_recalculated_at
  )
  VALUES (
    p_empresa_id,
    p_period_month,
    v_ingresos,
    v_gastos,
    v_ebitda,
    now()
  )
  ON CONFLICT (empresa_id, period_month)
  DO UPDATE SET
    ingresos_operacion = EXCLUDED.ingresos_operacion,
    gastos_operacion = EXCLUDED.gastos_operacion,
    ebitda = EXCLUDED.ebitda,
    last_recalculated_at = EXCLUDED.last_recalculated_at;
END;
$$;

CREATE OR REPLACE FUNCTION public.recalculate_monthly_kpis()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_old_empresa uuid;
  v_new_empresa uuid;
  v_old_month text;
  v_new_month text;
BEGIN
  IF TG_TABLE_NAME = 'facturas' THEN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
      v_old_empresa := OLD.empresa_id;
      v_old_month := to_char(COALESCE(OLD.fecha_emision, OLD.fecha::date, OLD.fecha_factura::date), 'YYYY-MM');
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
      v_new_empresa := NEW.empresa_id;
      v_new_month := to_char(COALESCE(NEW.fecha_emision, NEW.fecha::date, NEW.fecha_factura::date), 'YYYY-MM');
    END IF;
  ELSIF TG_TABLE_NAME = 'gastos' THEN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
      v_old_empresa := OLD.empresa_id;
      v_old_month := to_char(OLD.fecha::date, 'YYYY-MM');
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
      v_new_empresa := NEW.empresa_id;
      v_new_month := to_char(NEW.fecha::date, 'YYYY-MM');
    END IF;
  END IF;

  IF v_old_empresa IS NOT NULL AND v_old_month IS NOT NULL THEN
    PERFORM public._upsert_monthly_kpis(v_old_empresa, v_old_month);
  END IF;

  IF v_new_empresa IS NOT NULL
     AND v_new_month IS NOT NULL
     AND (v_new_empresa IS DISTINCT FROM v_old_empresa OR v_new_month IS DISTINCT FROM v_old_month) THEN
    PERFORM public._upsert_monthly_kpis(v_new_empresa, v_new_month);
  END IF;

  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_recalculate_monthly_kpis_facturas ON public.facturas;
CREATE TRIGGER trg_recalculate_monthly_kpis_facturas
AFTER INSERT OR UPDATE OR DELETE
ON public.facturas
FOR EACH ROW
EXECUTE FUNCTION public.recalculate_monthly_kpis();

DROP TRIGGER IF EXISTS trg_recalculate_monthly_kpis_gastos ON public.gastos;
CREATE TRIGGER trg_recalculate_monthly_kpis_gastos
AFTER INSERT OR UPDATE OR DELETE
ON public.gastos
FOR EACH ROW
EXECUTE FUNCTION public.recalculate_monthly_kpis();

COMMIT;


-- ============================================================================
-- [26/71] END FILE: 20260319000025_finance_snapshots.sql
-- ============================================================================

-- ============================================================================
-- [27/71] BEGIN FILE: 20260319000026_maps_distance_cache.sql
-- ============================================================================

-- Caché global de distancias Google Distance Matrix (reduce costes API).
CREATE TABLE IF NOT EXISTS public.maps_distance_cache (
  id BIGSERIAL PRIMARY KEY,
  cache_key TEXT NOT NULL UNIQUE,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  distance_km NUMERIC(12, 4) NOT NULL CHECK (distance_km >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_maps_distance_cache_updated
  ON public.maps_distance_cache (updated_at DESC);

COMMENT ON TABLE public.maps_distance_cache IS
  'Caché de distancias carretera (km) entre origen/destino; clave hash normalizada.';

ALTER TABLE public.maps_distance_cache ENABLE ROW LEVEL SECURITY;

-- Lectura/escritura para cualquier rol autenticado (JWT); la clave no expone secretos.
DROP POLICY IF EXISTS maps_distance_cache_authenticated_all ON public.maps_distance_cache;
CREATE POLICY maps_distance_cache_authenticated_all
  ON public.maps_distance_cache
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);


-- ============================================================================
-- [27/71] END FILE: 20260319000026_maps_distance_cache.sql
-- ============================================================================

-- ============================================================================
-- [28/71] BEGIN FILE: 20260319000027_verifactu_huella_chain.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS huella_hash varchar(64),
  ADD COLUMN IF NOT EXISTS huella_anterior varchar(64),
  ADD COLUMN IF NOT EXISTS fecha_hitos_verifactu timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ux_facturas_empresa_huella_hash'
  ) THEN
    ALTER TABLE public.facturas
      ADD CONSTRAINT ux_facturas_empresa_huella_hash
      UNIQUE (empresa_id, huella_hash);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_facturas_empresa_huella_seq
  ON public.facturas (empresa_id, numero_secuencial DESC);

UPDATE public.facturas
SET
  huella_hash = COALESCE(NULLIF(TRIM(huella_hash), ''), NULLIF(TRIM(hash_registro), ''), NULLIF(TRIM(hash_factura), '')),
  huella_anterior = COALESCE(NULLIF(TRIM(huella_anterior), ''), NULLIF(TRIM(hash_anterior), '')),
  fecha_hitos_verifactu = COALESCE(fecha_hitos_verifactu, now())
WHERE
  huella_hash IS NULL
  OR huella_anterior IS NULL
  OR fecha_hitos_verifactu IS NULL;

COMMIT;


-- ============================================================================
-- [28/71] END FILE: 20260319000027_verifactu_huella_chain.sql
-- ============================================================================

-- ============================================================================
-- [29/71] BEGIN FILE: 20260319000028_esg_flota_porte_vehiculo.sql
-- ============================================================================

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


-- ============================================================================
-- [29/71] END FILE: 20260319000028_esg_flota_porte_vehiculo.sql
-- ============================================================================

-- ============================================================================
-- [30/71] BEGIN FILE: 20260319000029_bank_integration.sql
-- ============================================================================

-- Open Banking (GoCardless): cuentas cifradas, historial de movimientos y vínculo con facturas.

-- ─── Cuenta bancaria por empresa (requisition / account IDs cifrados en aplicación como texto Fernet) ───
CREATE TABLE IF NOT EXISTS public.empresa_bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  requisition_id_enc TEXT NOT NULL,
  account_id_enc TEXT,
  institution_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT empresa_bank_accounts_empresa_unique UNIQUE (empresa_id)
);

COMMENT ON TABLE public.empresa_bank_accounts IS
  'GoCardless: requisition_id y account_id cifrados (Fernet) antes de persistir.';
COMMENT ON COLUMN public.empresa_bank_accounts.requisition_id_enc IS 'Ciphertext Fernet (base64) del requisition UUID';
COMMENT ON COLUMN public.empresa_bank_accounts.account_id_enc IS 'Ciphertext Fernet del account_id GoCardless (primera cuenta o selección)';

CREATE INDEX IF NOT EXISTS idx_empresa_bank_accounts_empresa ON public.empresa_bank_accounts (empresa_id);

-- Copia desde tabla legada si existe (mismos ciphertexts).
INSERT INTO public.empresa_bank_accounts (empresa_id, requisition_id_enc, institution_id, created_at, updated_at)
SELECT ebs.empresa_id, ebs.requisition_id_enc, ebs.institution_id, ebs.created_at, ebs.updated_at
FROM public.empresa_banco_sync AS ebs
ON CONFLICT (empresa_id) DO NOTHING;

-- ─── Movimientos importados (conciliación; sin PII en logs de aplicación) ───
CREATE TABLE IF NOT EXISTS public.bank_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  transaction_id TEXT NOT NULL,
  amount NUMERIC(18, 2) NOT NULL,
  booked_date DATE NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  description TEXT,
  reconciled BOOLEAN NOT NULL DEFAULT false,
  raw_fingerprint TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT bank_transactions_empresa_tx_unique UNIQUE (empresa_id, transaction_id)
);

COMMENT ON TABLE public.bank_transactions IS 'Movimientos bancarios sincronizados (GoCardless); conciliación automática opcional.';
COMMENT ON COLUMN public.bank_transactions.raw_fingerprint IS 'Hash opcional para deduplicar sin almacenar payload crudo';

CREATE INDEX IF NOT EXISTS idx_bank_transactions_empresa_booked ON public.bank_transactions (empresa_id, booked_date DESC);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_empresa_reconciled ON public.bank_transactions (empresa_id, reconciled);

-- ─── Facturas: vínculo explícito y fecha real de cobro ───
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS matched_transaction_id TEXT,
  ADD COLUMN IF NOT EXISTS fecha_cobro_real DATE;

COMMENT ON COLUMN public.facturas.matched_transaction_id IS 'transaction_id bancario emparejado en conciliación automática';
COMMENT ON COLUMN public.facturas.fecha_cobro_real IS 'Fecha contable del cobro (p. ej. bookingDate del movimiento)';

-- ─── RLS tenant ───
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'empresa_bank_accounts'
  ) THEN
    ALTER TABLE public.empresa_bank_accounts ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS empresa_bank_accounts_tenant_all ON public.empresa_bank_accounts;
    CREATE POLICY empresa_bank_accounts_tenant_all ON public.empresa_bank_accounts
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'bank_transactions'
  ) THEN
    ALTER TABLE public.bank_transactions ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_transactions_tenant_all ON public.bank_transactions;
    CREATE POLICY bank_transactions_tenant_all ON public.bank_transactions
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;


-- ============================================================================
-- [30/71] END FILE: 20260319000029_bank_integration.sql
-- ============================================================================

-- ============================================================================
-- [31/71] BEGIN FILE: 20260319000030_infra_health_logs.sql
-- ============================================================================

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


-- ============================================================================
-- [31/71] END FILE: 20260319000030_infra_health_logs.sql
-- ============================================================================

-- ============================================================================
-- [32/71] BEGIN FILE: 20260319000031_portes_activos_math_engine_view.sql
-- ============================================================================

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


-- ============================================================================
-- [32/71] END FILE: 20260319000031_portes_activos_math_engine_view.sql
-- ============================================================================

-- ============================================================================
-- [33/71] BEGIN FILE: 20260319000032_rbac_user_role_profiles_portes_rls.sql
-- ============================================================================

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


-- ============================================================================
-- [33/71] END FILE: 20260319000032_rbac_user_role_profiles_portes_rls.sql
-- ============================================================================

-- ============================================================================
-- [34/71] BEGIN FILE: 20260319000033_bank_accounts_transactions_open_banking.sql
-- ============================================================================

-- Mirror of supabase/migrations/20260413_bank_accounts_transactions_open_banking.sql

CREATE TABLE IF NOT EXISTS public.bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  gocardless_account_id TEXT NOT NULL,
  institution_id TEXT,
  iban_masked TEXT,
  currency TEXT NOT NULL DEFAULT 'EUR',
  status TEXT NOT NULL DEFAULT 'linked',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT bank_accounts_empresa_gc_account UNIQUE (empresa_id, gocardless_account_id)
);

COMMENT ON TABLE public.bank_accounts IS
  'Cuentas bancarias enlazadas vía GoCardless Bank Account Data (Nordigen); un registro por account_id de la API.';

CREATE INDEX IF NOT EXISTS idx_bank_accounts_empresa ON public.bank_accounts (empresa_id);

ALTER TABLE public.bank_transactions
  ADD COLUMN IF NOT EXISTS bank_account_id UUID REFERENCES public.bank_accounts (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS gocardless_account_id TEXT,
  ADD COLUMN IF NOT EXISTS remittance_info TEXT,
  ADD COLUMN IF NOT EXISTS internal_status TEXT NOT NULL DEFAULT 'imported';

CREATE INDEX IF NOT EXISTS idx_bank_transactions_gc_account ON public.bank_transactions (empresa_id, gocardless_account_id);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'bank_accounts'
  ) THEN
    ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_accounts_tenant_all ON public.bank_accounts;
    CREATE POLICY bank_accounts_tenant_all ON public.bank_accounts
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;


-- ============================================================================
-- [34/71] END FILE: 20260319000033_bank_accounts_transactions_open_banking.sql
-- ============================================================================

-- ============================================================================
-- [35/71] BEGIN FILE: 20260319000034_bank_accounts_transactions_open_banking.sql
-- ============================================================================

-- Open Banking: cuentas enlazadas por empresa + columnas de movimiento alineadas al contrato API.

CREATE TABLE IF NOT EXISTS public.bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  gocardless_account_id TEXT NOT NULL,
  institution_id TEXT,
  iban_masked TEXT,
  currency TEXT NOT NULL DEFAULT 'EUR',
  status TEXT NOT NULL DEFAULT 'linked',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT bank_accounts_empresa_gc_account UNIQUE (empresa_id, gocardless_account_id)
);

COMMENT ON TABLE public.bank_accounts IS
  'Cuentas bancarias enlazadas vía GoCardless Bank Account Data (Nordigen); un registro por account_id de la API.';
COMMENT ON COLUMN public.bank_accounts.gocardless_account_id IS 'UUID de cuenta devuelto por GET /requisitions/{id}/ (accounts[])';
COMMENT ON COLUMN public.bank_accounts.iban_masked IS 'Últimos dígitos o máscara para UI (sin IBAN completo en claro si no es necesario)';

CREATE INDEX IF NOT EXISTS idx_bank_accounts_empresa ON public.bank_accounts (empresa_id);

ALTER TABLE public.bank_transactions
  ADD COLUMN IF NOT EXISTS bank_account_id UUID REFERENCES public.bank_accounts (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS gocardless_account_id TEXT,
  ADD COLUMN IF NOT EXISTS remittance_info TEXT,
  ADD COLUMN IF NOT EXISTS internal_status TEXT NOT NULL DEFAULT 'imported';

COMMENT ON COLUMN public.bank_transactions.booked_date IS 'Fecha contable del apunte (equivalente Open Banking bookingDate)';
COMMENT ON COLUMN public.bank_transactions.remittance_info IS 'remittanceInformationUnstructured / array agregado';
COMMENT ON COLUMN public.bank_transactions.internal_status IS 'imported | reconciled (flujo interno; reconciled boolean sigue existiendo)';

CREATE INDEX IF NOT EXISTS idx_bank_transactions_gc_account ON public.bank_transactions (empresa_id, gocardless_account_id);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'bank_accounts'
  ) THEN
    ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_accounts_tenant_all ON public.bank_accounts;
    CREATE POLICY bank_accounts_tenant_all ON public.bank_accounts
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;


-- ============================================================================
-- [35/71] END FILE: 20260319000034_bank_accounts_transactions_open_banking.sql
-- ============================================================================

-- ============================================================================
-- [36/71] BEGIN FILE: 20260319000035_audit_logs_triggers.sql
-- ============================================================================

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


-- ============================================================================
-- [36/71] END FILE: 20260319000035_audit_logs_triggers.sql
-- ============================================================================

-- ============================================================================
-- [37/71] BEGIN FILE: 20260319000036_verifactu_fingerprint_finalizacion.sql
-- ============================================================================

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


-- ============================================================================
-- [37/71] END FILE: 20260319000036_verifactu_fingerprint_finalizacion.sql
-- ============================================================================

-- ============================================================================
-- [38/71] BEGIN FILE: 20260319000037_aeat_verifactu_envios.sql
-- ============================================================================

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

-- ============================================================================
-- [38/71] END FILE: 20260319000037_aeat_verifactu_envios.sql
-- ============================================================================

-- ============================================================================
-- [39/71] BEGIN FILE: 20260319000038_webhooks_rate_limit.sql
-- ============================================================================

-- Webhooks salientes (integración con sistemas del cliente) + índices.
-- Ejecutar tras existir public.empresas.

CREATE TABLE IF NOT EXISTS public.webhook_endpoints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  url text NOT NULL,
  secret text NOT NULL,
  events text[] NOT NULL DEFAULT '{}',
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_empresa_active
  ON public.webhook_endpoints (empresa_id)
  WHERE active = true;

CREATE TABLE IF NOT EXISTS public.webhook_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  webhook_endpoint_id uuid REFERENCES public.webhook_endpoints(id) ON DELETE SET NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  request_body text,
  response_status int,
  attempts int NOT NULL DEFAULT 0,
  failed_attempts int NOT NULL DEFAULT 0,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_empresa_created
  ON public.webhook_logs (empresa_id, created_at DESC);

ALTER TABLE public.webhook_endpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS webhook_endpoints_tenant_all ON public.webhook_endpoints;
CREATE POLICY webhook_endpoints_tenant_all ON public.webhook_endpoints
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

DROP POLICY IF EXISTS webhook_logs_tenant_all ON public.webhook_logs;
CREATE POLICY webhook_logs_tenant_all ON public.webhook_logs
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);


-- ============================================================================
-- [39/71] END FILE: 20260319000038_webhooks_rate_limit.sql
-- ============================================================================

-- ============================================================================
-- [40/71] BEGIN FILE: 20260319000039_vehiculos_gps_ultima.sql
-- ============================================================================

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


-- ============================================================================
-- [40/71] END FILE: 20260319000039_vehiculos_gps_ultima.sql
-- ============================================================================

-- ============================================================================
-- [41/71] BEGIN FILE: 20260319000040_movimientos_bancarios.sql
-- ============================================================================

-- Movimientos bancarios para conciliación (IA + aprobación humana).
-- facturas.id en este proyecto es BIGINT (ver README_SCHEMA_SYNC.md).

CREATE TABLE IF NOT EXISTS public.movimientos_bancarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  fecha date NOT NULL,
  concepto text NOT NULL DEFAULT '',
  importe numeric(18, 2) NOT NULL,
  iban_origen text,
  factura_id bigint REFERENCES public.facturas(id) ON DELETE SET NULL,
  estado text NOT NULL DEFAULT 'Pendiente'
    CHECK (estado IN ('Pendiente', 'Sugerido', 'Conciliado')),
  confidence_score numeric(6, 5),
  razonamiento_ia text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_movimientos_bancarios_empresa_estado
  ON public.movimientos_bancarios (empresa_id, estado);

CREATE INDEX IF NOT EXISTS idx_movimientos_bancarios_factura
  ON public.movimientos_bancarios (factura_id)
  WHERE factura_id IS NOT NULL;

ALTER TABLE public.movimientos_bancarios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS movimientos_bancarios_tenant_all ON public.movimientos_bancarios;
CREATE POLICY movimientos_bancarios_tenant_all ON public.movimientos_bancarios
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

COMMENT ON TABLE public.movimientos_bancarios IS
  'Movimientos para conciliación con facturas; estados Pendiente / Sugerido (IA) / Conciliado.';


-- ============================================================================
-- [41/71] END FILE: 20260319000040_movimientos_bancarios.sql
-- ============================================================================

-- ============================================================================
-- [42/71] BEGIN FILE: 20260319000041_treasury_vencimientos.sql
-- ============================================================================

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


-- ============================================================================
-- [42/71] END FILE: 20260319000041_treasury_vencimientos.sql
-- ============================================================================

-- ============================================================================
-- [43/71] BEGIN FILE: 20260319000042_portes_cmr_conductor.sql
-- ============================================================================

-- CMR: nombre del conductor (opcional; si NULL, el PDF deja la casilla en blanco).
ALTER TABLE public.portes ADD COLUMN IF NOT EXISTS conductor_nombre text;

COMMENT ON COLUMN public.portes.conductor_nombre IS
  'Nombre del conductor para carta de porte (CMR); opcional.';


-- ============================================================================
-- [43/71] END FILE: 20260319000042_portes_cmr_conductor.sql
-- ============================================================================

-- ============================================================================
-- [44/71] BEGIN FILE: 20260319000043_clientes_cuenta_contable.sql
-- ============================================================================

-- Cuenta contable PGC opcional por cliente (exportación a gestoría).
ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS cuenta_contable text;

COMMENT ON COLUMN public.clientes.cuenta_contable IS
  'Cuenta 430… si se informa; si NULL, la exportación genera 430 + sufijo determinista desde id.';


-- ============================================================================
-- [44/71] END FILE: 20260319000043_clientes_cuenta_contable.sql
-- ============================================================================

-- ============================================================================
-- [45/71] BEGIN FILE: 20260319000044_portes_firma_entrega_pod.sql
-- ============================================================================

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


-- ============================================================================
-- [45/71] END FILE: 20260319000044_portes_firma_entrega_pod.sql
-- ============================================================================

-- ============================================================================
-- [46/71] BEGIN FILE: 20260319000045_fix_rls_leaks.sql
-- ============================================================================

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


-- ============================================================================
-- [46/71] END FILE: 20260319000045_fix_rls_leaks.sql
-- ============================================================================

-- ============================================================================
-- [47/71] BEGIN FILE: 20260319000046_gastos_vehiculo_import.sql
-- ============================================================================

-- =============================================================================
-- gastos_vehiculo: importación de combustible / gastos asignados a vehículo
-- =============================================================================
-- Crea una tabla auxiliar (no sustituye `public.gastos`) para enlazar
-- los gastos importados (p. ej. tickets de combustible) a `vehiculo_id`
-- y permitir reporting / prevención de fraude por matrículas.
--
-- Multi-tenant: RLS por `empresa_id` usando `public.app_current_empresa_id()::text`
-- (ver 20260324_rls_tenant_current_empresa.sql).
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.gastos_vehiculo (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  vehiculo_id uuid NOT NULL REFERENCES public.vehiculos(id) ON DELETE CASCADE,
  gasto_id text,
  fecha date NOT NULL,
  categoria text NOT NULL DEFAULT 'Combustible',
  proveedor text,
  estacion text,
  matricula_normalizada text,
  litros numeric(18, 4) NOT NULL DEFAULT 0,
  importe_total numeric(18, 2) NOT NULL,
  moneda text NOT NULL DEFAULT 'EUR',
  concepto text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_gastos_vehiculo_empresa_fecha
  ON public.gastos_vehiculo (empresa_id, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_gastos_vehiculo_empresa_vehiculo
  ON public.gastos_vehiculo (empresa_id, vehiculo_id);

ALTER TABLE public.gastos_vehiculo ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS gastos_vehiculo_tenant_all ON public.gastos_vehiculo;
CREATE POLICY gastos_vehiculo_tenant_all ON public.gastos_vehiculo
  FOR ALL
  TO authenticated
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

COMMENT ON TABLE public.gastos_vehiculo IS
  'Auxiliar: gastos importados enlazados a vehiculo_id (p. ej. combustible) con aislamiento multi-tenant por empresa_id (RLS).';



-- ============================================================================
-- [47/71] END FILE: 20260319000046_gastos_vehiculo_import.sql
-- ============================================================================

-- ============================================================================
-- [48/71] BEGIN FILE: 20260319000047_esg_auditoria_fuel_import.sql
-- ============================================================================

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



-- ============================================================================
-- [48/71] END FILE: 20260319000047_esg_auditoria_fuel_import.sql
-- ============================================================================

-- ============================================================================
-- [49/71] BEGIN FILE: 20260319000048_audit_logs_append_only_security.sql
-- ============================================================================

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



-- ============================================================================
-- [49/71] END FILE: 20260319000048_audit_logs_append_only_security.sql
-- ============================================================================

-- ============================================================================
-- [50/71] BEGIN FILE: 20260319000049_audit_logs_select_strict_admin.sql
-- ============================================================================

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



-- ============================================================================
-- [50/71] END FILE: 20260319000049_audit_logs_select_strict_admin.sql
-- ============================================================================

-- ============================================================================
-- [51/71] BEGIN FILE: 20260319000050_webhooks_b2b.sql
-- ============================================================================

-- Webhooks B2B: una fila por suscripción (empresa + event_type + URL).
-- RLS: solo rol owner (ADMIN en API) puede gestionar; el backend con service role envía.

CREATE TABLE IF NOT EXISTS public.webhooks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  event_type text NOT NULL,
  target_url text NOT NULL,
  secret_key text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhooks_empresa_event_active
  ON public.webhooks (empresa_id, event_type)
  WHERE is_active = true;

ALTER TABLE public.webhooks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS webhooks_select_owner ON public.webhooks;
CREATE POLICY webhooks_select_owner ON public.webhooks
  FOR SELECT
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

DROP POLICY IF EXISTS webhooks_insert_owner ON public.webhooks;
CREATE POLICY webhooks_insert_owner ON public.webhooks
  FOR INSERT
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

DROP POLICY IF EXISTS webhooks_update_owner ON public.webhooks;
CREATE POLICY webhooks_update_owner ON public.webhooks
  FOR UPDATE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  )
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

DROP POLICY IF EXISTS webhooks_delete_owner ON public.webhooks;
CREATE POLICY webhooks_delete_owner ON public.webhooks
  FOR DELETE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

COMMENT ON TABLE public.webhooks IS
  'Webhooks salientes B2B por evento; RLS solo owner (ADMIN).';

ALTER TABLE public.webhook_logs
  ADD COLUMN IF NOT EXISTS webhook_id uuid REFERENCES public.webhooks (id) ON DELETE SET NULL;


-- ============================================================================
-- [51/71] END FILE: 20260319000050_webhooks_b2b.sql
-- ============================================================================

-- ============================================================================
-- [52/71] BEGIN FILE: 20260319000051_fleet_maintenance.sql
-- ============================================================================

-- Mantenimiento predictivo por km: odómetro y planes por vehículo (flota).
-- portes.vehiculo_id referencia public.flota(id); odometro_actual se actualiza al completar entrega.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS odometro_actual integer NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.flota.odometro_actual IS
  'Km acumulados operativos (suma de km de portes completados); independiente de km_actual legacy.';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    EXECUTE '
      ALTER TABLE public.vehiculos
        ADD COLUMN IF NOT EXISTS odometro_actual integer NOT NULL DEFAULT 0
    ';
    EXECUTE '
      COMMENT ON COLUMN public.vehiculos.odometro_actual IS
        ''Odómetro operativo (sincronizado con flota cuando comparten id de vehículo).''
    ';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.planes_mantenimiento (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  vehiculo_id uuid NOT NULL REFERENCES public.flota (id) ON DELETE CASCADE,
  tipo_tarea text NOT NULL,
  intervalo_km integer NOT NULL CHECK (intervalo_km > 0),
  ultimo_km_realizado integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_planes_mantenimiento_empresa_vehiculo
  ON public.planes_mantenimiento (empresa_id, vehiculo_id);

ALTER TABLE public.planes_mantenimiento ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS planes_mantenimiento_select_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_select_rbac ON public.planes_mantenimiento
  FOR SELECT
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

DROP POLICY IF EXISTS planes_mantenimiento_insert_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_insert_rbac ON public.planes_mantenimiento
  FOR INSERT
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

DROP POLICY IF EXISTS planes_mantenimiento_update_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_update_rbac ON public.planes_mantenimiento
  FOR UPDATE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  )
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

DROP POLICY IF EXISTS planes_mantenimiento_delete_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_delete_rbac ON public.planes_mantenimiento
  FOR DELETE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

COMMENT ON TABLE public.planes_mantenimiento IS
  'Planes de mantenimiento por intervalo de km; visión owner/traffic_manager (ADMIN/GESTOR).';

-- Incremento atómico de odómetro al completar porte (JWT + app_current_empresa_id).
CREATE OR REPLACE FUNCTION public.increment_vehiculo_odometro(
  p_empresa_id uuid,
  p_vehiculo_id uuid,
  p_km numeric
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_add integer;
BEGIN
  IF p_km IS NULL OR p_km <= 0 THEN
    RETURN;
  END IF;
  v_add := GREATEST(1, CEIL(p_km)::integer);
  IF p_empresa_id::text IS DISTINCT FROM public.app_current_empresa_id()::text THEN
    RAISE EXCEPTION 'increment_vehiculo_odometro: empresa no coincide con la sesión';
  END IF;

  UPDATE public.flota f
  SET odometro_actual = COALESCE(f.odometro_actual, 0) + v_add
  WHERE f.id = p_vehiculo_id
    AND f.empresa_id = p_empresa_id
    AND f.deleted_at IS NULL;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    UPDATE public.vehiculos v
    SET odometro_actual = COALESCE(v.odometro_actual, 0) + v_add
    WHERE v.id = p_vehiculo_id
      AND v.empresa_id = p_empresa_id
      AND (v.deleted_at IS NULL);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.increment_vehiculo_odometro(uuid, uuid, numeric) IS
  'Suma km al odómetro en flota (y vehiculos si existe fila con mismo id). Requiere app_current_empresa_id.';

GRANT EXECUTE ON FUNCTION public.increment_vehiculo_odometro(uuid, uuid, numeric) TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_vehiculo_odometro(uuid, uuid, numeric) TO service_role;


-- ============================================================================
-- [52/71] END FILE: 20260319000051_fleet_maintenance.sql
-- ============================================================================

-- ============================================================================
-- [53/71] BEGIN FILE: 20260319000052_schema_sync_esg_treasury_pod_gin.sql
-- ============================================================================

-- Sincronización final (auditoría): ESG combustible + tesorería/VeriFactu + POD + GIN analítico.
-- Idempotente: IF NOT EXISTS / CREATE OR REPLACE donde aplica.

-- ─── ESG: certificación motor (Euro V / VI / …) en flota y vehículos ─────────
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

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS co2_emitido numeric;

COMMENT ON COLUMN public.portes.co2_emitido IS
  'kg CO2 estimados en el porte (motor ESG / distancia).';

-- Vista resumen (requiere co2_emitido en portes; COALESCE en SELECT).
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

-- ─── ESG auditoría combustible: CO2 automático (litros × factor × norma motor) ─
CREATE OR REPLACE FUNCTION public.esg_auditoria_calc_co2()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid := NEW.empresa_id;
  v_vid uuid := NEW.vehiculo_id;
  v_lit numeric := COALESCE(NEW.litros_consumidos, 0);
  v_cert text;
  v_base_kg_per_l numeric;
  v_norma numeric;
  v_tipo text;
BEGIN
  IF v_lit IS NULL OR v_lit <= 0 THEN
    NEW.co2_emitido_kg := 0;
    RETURN NEW;
  END IF;

  SELECT COALESCE(
    (SELECT certificacion_emisiones FROM public.vehiculos v
     WHERE v.id = v_vid AND v.empresa_id = v_empresa AND v.deleted_at IS NULL LIMIT 1),
    (SELECT certificacion_emisiones FROM public.flota f
     WHERE f.id = v_vid AND f.empresa_id = v_empresa AND f.deleted_at IS NULL LIMIT 1),
    'Euro VI'
  ) INTO v_cert;

  v_tipo := lower(trim(coalesce(NEW.tipo_combustible, '')));

  -- kg CO2 por litro (combustión aprox.); alineado con reporting transporte.
  v_base_kg_per_l := CASE
    WHEN v_tipo LIKE '%elect%' THEN 0
    WHEN v_tipo LIKE '%gasolina%' THEN 2.31
    WHEN v_tipo LIKE '%glp%' OR v_tipo LIKE '%gnc%' THEN 1.67
    ELSE 2.65
  END;

  v_norma := CASE trim(coalesce(v_cert, 'Euro VI'))
    WHEN 'Euro VI' THEN 1.0
    WHEN 'Euro V' THEN 1.15
    WHEN 'Electrico' THEN 0
    WHEN 'Hibrido' THEN 0.55
    ELSE 1.0
  END;

  NEW.co2_emitido_kg := round((v_lit * v_base_kg_per_l * v_norma)::numeric, 6);
  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.esg_auditoria_calc_co2() IS
  'Calcula co2_emitido_kg en esg_auditoria: litros × factor combustible × certificación motor (Euro VI baseline).';

DROP TRIGGER IF EXISTS trg_esg_auditoria_calc_co2 ON public.esg_auditoria;
CREATE TRIGGER trg_esg_auditoria_calc_co2
  BEFORE INSERT OR UPDATE OF litros_consumidos, vehiculo_id, tipo_combustible
  ON public.esg_auditoria
  FOR EACH ROW
  EXECUTE FUNCTION public.esg_auditoria_calc_co2();

-- ─── Tesorería: vencimiento cobro + fecha estimada ligada a VeriFactu enviado_ok ─
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fecha_vencimiento date;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fecha_estimada_cobro date;

COMMENT ON COLUMN public.facturas.fecha_vencimiento IS
  'Vencimiento de cobro (AR); si NULL, la API puede usar fecha_emision + 30 días.';
COMMENT ON COLUMN public.facturas.fecha_estimada_cobro IS
  'Previsión de cobro; se rellena al pasar aeat_sif_estado a enviado_ok (baseline: vencimiento o emisión+30d).';

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS aeat_sif_estado text;

CREATE OR REPLACE FUNCTION public.facturas_sync_fecha_estimada_cobro()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_base date;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.aeat_sif_estado IS DISTINCT FROM OLD.aeat_sif_estado
       AND lower(trim(coalesce(NEW.aeat_sif_estado, ''))) = 'enviado_ok'
    THEN
      IF NEW.fecha_vencimiento IS NOT NULL THEN
        NEW.fecha_estimada_cobro := NEW.fecha_vencimiento;
      ELSE
        v_base := COALESCE(NEW.fecha_emision, NEW.fecha, NEW.fecha_factura, CURRENT_DATE);
        NEW.fecha_estimada_cobro := (v_base + INTERVAL '30 days')::date;
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_estimada_cobro_verifactu ON public.facturas;
CREATE TRIGGER trg_facturas_estimada_cobro_verifactu
  BEFORE UPDATE OF aeat_sif_estado ON public.facturas
  FOR EACH ROW
  EXECUTE FUNCTION public.facturas_sync_fecha_estimada_cobro();

COMMENT ON FUNCTION public.facturas_sync_fecha_estimada_cobro() IS
  'Si aeat_sif_estado pasa a enviado_ok, fija fecha_estimada_cobro (prioriza fecha_vencimiento).';

-- ─── POD: firma inline (base64) y URL de almacenamiento (bucket / CDN) ───────
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS firma_consignatario_b64 text,
  ADD COLUMN IF NOT EXISTS firma_consignatario_url text,
  ADD COLUMN IF NOT EXISTS nombre_consignatario_final text,
  ADD COLUMN IF NOT EXISTS fecha_entrega_real timestamptz,
  ADD COLUMN IF NOT EXISTS conductor_asignado_id uuid REFERENCES public.profiles (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.portes.firma_consignatario_b64 IS
  'Firma PNG/SVG en Base64 (data URL o raw); alternativa a URL en bucket.';
COMMENT ON COLUMN public.portes.firma_consignatario_url IS
  'URL pública o firmada (p. ej. Storage) si la firma no va en fila.';
COMMENT ON COLUMN public.portes.nombre_consignatario_final IS 'Nombre de quien firma la entrega.';
COMMENT ON COLUMN public.portes.fecha_entrega_real IS 'Marca hora de la entrega confirmada.';
COMMENT ON COLUMN public.portes.conductor_asignado_id IS 'Perfil (profiles.id) conductor explícito.';

-- ─── Índices GIN (jsonb) para analítica / dashboard ───────────────────────────
CREATE INDEX IF NOT EXISTS idx_facturas_items_gin
  ON public.facturas USING GIN (items);

CREATE INDEX IF NOT EXISTS idx_facturas_datos_json_gin
  ON public.facturas USING GIN (datos_json);

CREATE INDEX IF NOT EXISTS idx_facturas_porte_lineas_snapshot_gin
  ON public.facturas USING GIN (porte_lineas_snapshot);

CREATE INDEX IF NOT EXISTS idx_audit_logs_old_data_gin
  ON public.audit_logs USING GIN (old_data)
  WHERE old_data IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_logs_new_data_gin
  ON public.audit_logs USING GIN (new_data)
  WHERE new_data IS NOT NULL;

COMMENT ON INDEX idx_facturas_items_gin IS 'Búsqueda analítica en líneas JSON de factura.';
COMMENT ON INDEX idx_audit_logs_old_data_gin IS 'Filtros JSON en trazas de auditoría (old_data).';


-- ============================================================================
-- [53/71] END FILE: 20260319000052_schema_sync_esg_treasury_pod_gin.sql
-- ============================================================================

-- ============================================================================
-- [54/71] BEGIN FILE: 20260319000053_flota_fechas_administrativas.sql
-- ============================================================================

-- Fechas administrativas (ITV, seguro, tacógrafo) en inventario flota.
-- Compatibilidad: copia desde itv_vencimiento / seguro_vencimiento si las nuevas columnas están vacías.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS fecha_itv date,
  ADD COLUMN IF NOT EXISTS fecha_seguro date,
  ADD COLUMN IF NOT EXISTS fecha_tacografo date;

UPDATE public.flota
SET fecha_itv = itv_vencimiento
WHERE fecha_itv IS NULL AND itv_vencimiento IS NOT NULL;

UPDATE public.flota
SET fecha_seguro = seguro_vencimiento
WHERE fecha_seguro IS NULL AND seguro_vencimiento IS NOT NULL;

COMMENT ON COLUMN public.flota.fecha_itv IS 'Próxima ITV (fecha límite); preferente sobre itv_vencimiento legacy.';
COMMENT ON COLUMN public.flota.fecha_seguro IS 'Vencimiento póliza; preferente sobre seguro_vencimiento legacy.';
COMMENT ON COLUMN public.flota.fecha_tacografo IS 'Revisión / calibración tacógrafo (fecha límite).';


-- ============================================================================
-- [54/71] END FILE: 20260319000053_flota_fechas_administrativas.sql
-- ============================================================================

-- ============================================================================
-- [55/71] BEGIN FILE: 20260319000054_portes_dni_consignatario_pod.sql
-- ============================================================================

-- DNI/NIE opcional del consignatario (POD).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS dni_consignatario text;

COMMENT ON COLUMN public.portes.dni_consignatario IS 'DNI/NIE del consignatario (opcional, entrega POD).';


-- ============================================================================
-- [55/71] END FILE: 20260319000054_portes_dni_consignatario_pod.sql
-- ============================================================================

-- ============================================================================
-- [56/71] BEGIN FILE: 20260319000055_portal_cliente_rbac.sql
-- ============================================================================

-- Portal cliente (autoservicio): rol `cliente`, `profiles.cliente_id`, sesión app.cliente_id
-- y políticas RLS para portes/facturas/clientes sin fugas entre cargadores del mismo tenant.

-- ─── Enum user_role: valor cliente ───
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE n.nspname = 'public' AND t.typname = 'user_role')
     AND NOT EXISTS (
       SELECT 1 FROM pg_enum e
       JOIN pg_type t ON t.oid = e.enumtypid
       JOIN pg_namespace n ON n.oid = t.typnamespace
       WHERE n.nspname = 'public' AND t.typname = 'user_role' AND e.enumlabel = 'cliente'
     ) THEN
    ALTER TYPE public.user_role ADD VALUE 'cliente';
  END IF;
END $$;

-- ─── Perfil: vínculo al maestro clientes (portal) ───
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS cliente_id uuid REFERENCES public.clientes (id) ON DELETE SET NULL;
    COMMENT ON COLUMN public.profiles.cliente_id IS
      'FK clientes: usuario portal (rol cliente) asociado a un cargador concreto del tenant.';
  END IF;
END $$;

-- ─── Sesión: app.cliente_id + set_rbac_session extendido ───
CREATE OR REPLACE FUNCTION public.app_current_cliente_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(trim(both from current_setting('app.cliente_id', true)), '');
$$;

COMMENT ON FUNCTION public.app_current_cliente_id() IS
  'UUID texto del cliente (cargador) en sesión portal; vacío si no aplica.';

CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL,
  p_profile_id uuid DEFAULT NULL,
  p_cliente_id uuid DEFAULT NULL
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
  IF r NOT IN ('owner', 'traffic_manager', 'driver', 'cliente') THEN
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
  IF r = 'cliente' AND p_cliente_id IS NOT NULL THEN
    PERFORM set_config('app.cliente_id', p_cliente_id::text, true);
  ELSE
    PERFORM set_config('app.cliente_id', '', true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid, uuid) IS
  'Fija app.rbac_role, app.assigned_vehiculo_id, app.current_profile_id y app.cliente_id (portal).';

-- ─── PORTES: lectura para rol cliente (solo su cliente_id) ───
DO $$
BEGIN
  IF to_regclass('public.portes') IS NOT NULL THEN
    DROP POLICY IF EXISTS portes_select_cliente ON public.portes;
    CREATE POLICY portes_select_cliente ON public.portes
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() = 'cliente'
        AND cliente_id IS NOT NULL
        AND cliente_id::text = public.app_current_cliente_id()
      );
  END IF;
END $$;

-- ─── FACTURAS: reemplazar política amplia por RBAC + portal ───
DO $$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    DROP POLICY IF EXISTS facturas_tenant_all ON public.facturas;

    CREATE POLICY facturas_select_rbac ON public.facturas
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND (
          public.app_rbac_role() IN ('owner', 'traffic_manager', 'driver')
          OR (
            public.app_rbac_role() = 'cliente'
            AND cliente IS NOT NULL
            AND cliente::text = public.app_current_cliente_id()
          )
        )
      );

    CREATE POLICY facturas_insert_rbac ON public.facturas
      FOR INSERT
      TO authenticated
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY facturas_update_rbac ON public.facturas
      FOR UPDATE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY facturas_delete_rbac ON public.facturas
      FOR DELETE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;

-- ─── CLIENTES: staff vs portal (evitar listar todos los clientes del tenant) ───
DO $$
BEGIN
  IF to_regclass('public.clientes') IS NOT NULL THEN
    DROP POLICY IF EXISTS clientes_tenant_all ON public.clientes;

    CREATE POLICY clientes_select_staff ON public.clientes
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'driver')
      );

    CREATE POLICY clientes_select_portal ON public.clientes
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() = 'cliente'
        AND id::text = public.app_current_cliente_id()
      );

    CREATE POLICY clientes_insert_staff ON public.clientes
      FOR INSERT
      TO authenticated
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY clientes_update_staff ON public.clientes
      FOR UPDATE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY clientes_delete_staff ON public.clientes
      FOR DELETE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;


-- ============================================================================
-- [56/71] END FILE: 20260319000055_portal_cliente_rbac.sql
-- ============================================================================

-- ============================================================================
-- [57/71] BEGIN FILE: 20260319000056_portal_onboarding_risk_acceptance.sql
-- ============================================================================

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



-- ============================================================================
-- [57/71] END FILE: 20260319000056_portal_onboarding_risk_acceptance.sql
-- ============================================================================

-- ============================================================================
-- [58/71] BEGIN FILE: 20260319000057_audit_trail_process_audit_log.sql
-- ============================================================================

-- =============================================================================
-- Pista de auditoría inmutable: public.process_audit_log() + triggers
-- (facturas, portes, gastos, bank_transactions) + RPC audit_logs_insert_api_event
-- para inserciones desde la API con JWT. SELECT: solo owner del tenant activo.
-- =============================================================================

ALTER TYPE public.audit_action ADD VALUE IF NOT EXISTS 'INVITE_RESENT';

BEGIN;

-- Columnas opcionales (compat 20260438)
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS tabla_afectada text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS operacion text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS registro_id uuid;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS usuario_id uuid;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS fecha timestamptz;

-- ─── 1) Quitar triggers que dependen de las funciones antiguas ───────────────
DO $drop_trg$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas';
  END IF;
  IF to_regclass('public.portes') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes';
  END IF;
  IF to_regclass('public.gastos') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_gastos ON public.gastos';
  END IF;
  IF to_regclass('public.bank_transactions') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_bank_transactions ON public.bank_transactions';
  END IF;
END
$drop_trg$;

DROP FUNCTION IF EXISTS public.log_table_changes() CASCADE;
DROP FUNCTION IF EXISTS public.audit_row_change() CASCADE;

-- ─── 2) Función trigger canónica ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.process_audit_log()
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
  v_action public.audit_action;
  v_role text;
BEGIN
  v_role := public.app_rbac_role();

  IF TG_OP = 'INSERT' THEN
    v_action := 'INSERT'::public.audit_action;
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(
      NULLIF(trim(public.app_current_empresa_id()::text), '')::uuid,
      (NEW).empresa_id
    );
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE'::public.audit_action;
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(
      NULLIF(trim(public.app_current_empresa_id()::text), '')::uuid,
      (NEW).empresa_id,
      (OLD).empresa_id
    );
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE'::public.audit_action;
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := COALESCE(
      NULLIF(trim(public.app_current_empresa_id()::text), '')::uuid,
      (OLD).empresa_id
    );
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  IF v_new IS NOT NULL THEN
    v_new := jsonb_set(
      v_new,
      '{_audit_role}',
      to_jsonb(v_role),
      true
    );
  END IF;

  v_record_id_text := COALESCE(v_new ->> 'id', v_old ->> 'id');
  IF v_record_id_text IS NULL OR length(trim(v_record_id_text)) = 0 THEN
    v_record_id_text := gen_random_uuid()::text;
    v_record_id := NULL;
  ELSE
    BEGIN
      v_record_id := trim(v_record_id_text)::uuid;
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
    v_record_id_text,
    v_action,
    v_old,
    v_new,
    auth.uid(),
    TG_TABLE_NAME::text,
    TG_OP::text,
    v_record_id,
    auth.uid(),
    now()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.process_audit_log() IS
  'Trigger AFTER INSERT/UPDATE/DELETE: OLD/NEW → public.audit_logs (SECURITY DEFINER).';

-- ─── 3) Re-enganchar triggers ────────────────────────────────────────────────
DO $attach$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_facturas AFTER INSERT OR UPDATE OR DELETE ON public.facturas FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
  IF to_regclass('public.portes') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_portes AFTER INSERT OR UPDATE OR DELETE ON public.portes FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
  IF to_regclass('public.gastos') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_gastos AFTER INSERT OR UPDATE OR DELETE ON public.gastos FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
  IF to_regclass('public.bank_transactions') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_bank_transactions AFTER INSERT OR UPDATE OR DELETE ON public.bank_transactions FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
END
$attach$;

-- ─── 4) RPC: append desde API (JWT) ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.audit_logs_insert_api_event(
  p_empresa_id uuid,
  p_table_name text,
  p_record_id text,
  p_action text,
  p_old_data jsonb DEFAULT NULL,
  p_new_data jsonb DEFAULT NULL,
  p_changed_by uuid DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
  v_uid uuid;
  v_rec text;
  v_reg uuid;
  v_action public.audit_action;
  v_ok boolean;
BEGIN
  v_uid := auth.uid();
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'audit_logs_insert_api_event: auth.uid() requerido';
  END IF;

  v_ok := false;
  IF to_regclass('public.profiles') IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1
      FROM public.profiles p
      WHERE p.id = v_uid
        AND p.empresa_id = p_empresa_id
    ) INTO v_ok;
  END IF;

  IF NOT v_ok AND to_regclass('public.usuarios') IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1
      FROM public.usuarios u
      WHERE u.id::text = v_uid::text
        AND u.empresa_id = p_empresa_id
    ) INTO v_ok;
  END IF;

  IF NOT v_ok THEN
    RAISE EXCEPTION 'audit_logs_insert_api_event: usuario no pertenece a la empresa indicada';
  END IF;

  v_rec := NULLIF(trim(p_record_id), '');
  IF v_rec IS NULL OR length(v_rec) = 0 THEN
    v_rec := gen_random_uuid()::text;
    v_reg := NULL;
  ELSE
    BEGIN
      v_reg := v_rec::uuid;
    EXCEPTION
      WHEN others THEN
        v_reg := NULL;
    END;
  END IF;

  BEGIN
    v_action := upper(trim(p_action))::public.audit_action;
  EXCEPTION
    WHEN others THEN
      RAISE EXCEPTION 'audit_logs_insert_api_event: acción no válida: %', p_action;
  END;

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
    p_empresa_id,
    left(trim(p_table_name), 128),
    v_rec,
    v_action,
    p_old_data,
    p_new_data,
    COALESCE(p_changed_by, v_uid),
    left(trim(p_table_name), 128),
    upper(trim(p_action)),
    v_reg,
    COALESCE(p_changed_by, v_uid),
    now()
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.audit_logs_insert_api_event IS
  'Append-only vía API: valida pertenencia a empresa; devuelve id del log.';

REVOKE INSERT ON TABLE public.audit_logs FROM PUBLIC;
REVOKE INSERT ON TABLE public.audit_logs FROM authenticated;
REVOKE INSERT ON TABLE public.audit_logs FROM anon;

GRANT INSERT ON TABLE public.audit_logs TO service_role;

GRANT EXECUTE ON FUNCTION public.audit_logs_insert_api_event(
  uuid, text, text, text, jsonb, jsonb, uuid
) TO authenticated;

-- ─── 5) RLS: SELECT solo owner ───────────────────────────────────────────────
DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_select_tenant_admin ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_select_admin_only ON public.audit_logs;

CREATE POLICY audit_logs_select_owner_tenant ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

CREATE INDEX IF NOT EXISTS idx_audit_logs_empresa_table_record_created
  ON public.audit_logs (empresa_id, table_name, record_id, created_at DESC);

COMMIT;


-- ============================================================================
-- [58/71] END FILE: 20260319000057_audit_trail_process_audit_log.sql
-- ============================================================================

-- ============================================================================
-- [59/71] BEGIN FILE: 20260319000058_add_portes_co2_kg.sql
-- ============================================================================

-- Campo de emisiones simplificado para reportes financieros ESG.
alter table if exists public.portes
add column if not exists co2_kg numeric;

-- Backfill inicial desde campo legacy si existe valor.
update public.portes
set co2_kg = coalesce(co2_kg, co2_emitido)
where co2_kg is null;


-- ============================================================================
-- [59/71] END FILE: 20260319000058_add_portes_co2_kg.sql
-- ============================================================================

-- ============================================================================
-- [60/71] BEGIN FILE: 20260319000059_facturas_fingerprint_hash_chain.sql
-- ============================================================================

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


-- ============================================================================
-- [60/71] END FILE: 20260319000059_facturas_fingerprint_hash_chain.sql
-- ============================================================================

-- ============================================================================
-- [61/71] BEGIN FILE: 20260319000100_rls_jwt_strict_multi_tenant.sql
-- ============================================================================

-- Endurecimiento RLS multi-tenant por JWT (empresa_id) para tablas críticas.
-- Política objetivo:
--   USING (auth.jwt() ->> 'empresa_id' = empresa_id::text)
-- y WITH CHECK equivalente para escrituras.

DO $$
BEGIN
  -- CLIENTES
  IF to_regclass('public.clientes') IS NOT NULL THEN
    ALTER TABLE public.clientes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Read own empresa" ON public.clientes;
    DROP POLICY IF EXISTS "Write own empresa" ON public.clientes;
    DROP POLICY IF EXISTS "aislamiento_clientes" ON public.clientes;
    DROP POLICY IF EXISTS "rls_clientes" ON public.clientes;
    DROP POLICY IF EXISTS "tenant_isolation_clientes" ON public.clientes;
    DROP POLICY IF EXISTS clientes_tenant_jwt_all ON public.clientes;

    CREATE POLICY clientes_tenant_jwt_all
      ON public.clientes
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- PORTES
  IF to_regclass('public.portes') IS NOT NULL THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Acceso total por empresa_id" ON public.portes;
    DROP POLICY IF EXISTS "Usuarios crean portes para su empresa" ON public.portes;
    DROP POLICY IF EXISTS "Usuarios ven portes de su empresa" ON public.portes;
    DROP POLICY IF EXISTS "tenant_isolation_policy_portes" ON public.portes;
    DROP POLICY IF EXISTS portes_tenant_jwt_all ON public.portes;

    CREATE POLICY portes_tenant_jwt_all
      ON public.portes
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- FACTURAS
  IF to_regclass('public.facturas') IS NOT NULL THEN
    ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Empresas solo ven sus propias facturas" ON public.facturas;
    DROP POLICY IF EXISTS "Read own empresa" ON public.facturas;
    DROP POLICY IF EXISTS "Write own empresa" ON public.facturas;
    DROP POLICY IF EXISTS "crear_facturas_propias" ON public.facturas;
    DROP POLICY IF EXISTS "ver_facturas_propias" ON public.facturas;
    DROP POLICY IF EXISTS "rls_facturas" ON public.facturas;
    DROP POLICY IF EXISTS "tenant_isolation_policy_facturas" ON public.facturas;
    DROP POLICY IF EXISTS facturas_tenant_jwt_all ON public.facturas;

    CREATE POLICY facturas_tenant_jwt_all
      ON public.facturas
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- VEHICULOS
  IF to_regclass('public.vehiculos') IS NOT NULL THEN
    ALTER TABLE public.vehiculos ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Acceso por empresa en vehiculos" ON public.vehiculos;
    DROP POLICY IF EXISTS "tenant_isolation_policy_vehiculos" ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_tenant_jwt_all ON public.vehiculos;

    CREATE POLICY vehiculos_tenant_jwt_all
      ON public.vehiculos
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- GASTOS_VEHICULO
  IF to_regclass('public.gastos_vehiculo') IS NOT NULL THEN
    ALTER TABLE public.gastos_vehiculo ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS gastos_vehiculo_tenant_all ON public.gastos_vehiculo;
    DROP POLICY IF EXISTS gastos_vehiculo_tenant_jwt_all ON public.gastos_vehiculo;

    CREATE POLICY gastos_vehiculo_tenant_jwt_all
      ON public.gastos_vehiculo
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;
END $$;


-- ============================================================================
-- [61/71] END FILE: 20260319000100_rls_jwt_strict_multi_tenant.sql
-- ============================================================================

-- ============================================================================
-- [62/71] BEGIN FILE: 20260319000101_rbac_admin_staff_extension.sql
-- ============================================================================

-- =============================================================================
-- Extensión del sistema RBAC: añadir roles SUPERADMIN, ADMIN y STAFF
-- Migración segura que mantiene compatibilidad con roles existentes
-- =============================================================================

-- 1. Extender el tipo user_role con los nuevos valores
-- Se mantienen los valores existentes: owner, traffic_manager, driver
-- Se añaden: superadmin, admin, staff
DO $$ BEGIN
  -- Primero verificamos si el tipo existe
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    CREATE TYPE public.user_role AS ENUM ('owner', 'traffic_manager', 'driver');
  END IF;
  
  -- Añadir nuevos valores al enum si no existen
  BEGIN
    ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'superadmin';
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'admin';
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'staff';
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
END $$;

-- 2. Actualizar comentario del tipo para reflejar la nueva jerarquía
COMMENT ON TYPE public.user_role IS 
  'Roles RBAC del sistema. Jerarquía: superadmin (gestión cross-tenant), admin (gestión completa del tenant), staff (operaciones básicas), owner/traffic_manager/driver (roles operativos legados)';

-- 3. Añadir columna de auditoría en usuarios si no existe
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'usuarios'
  ) THEN
    -- Añadir columna role_rbac si no existe (para distinguir del rol operativo)
    ALTER TABLE public.usuarios
      ADD COLUMN IF NOT EXISTS role_rbac public.user_role NOT NULL DEFAULT 'staff'::public.user_role;
    
    COMMENT ON COLUMN public.usuarios.role_rbac IS
      'Rol RBAC de seguridad (superadmin/admin/staff). Controla acceso a secciones sensibles: finanzas, administración.';
  END IF;
END $$;

-- 4. Actualizar profiles con el nuevo sistema de roles
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    -- Añadir columna role_rbac también en profiles para consistencia
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS role_rbac public.user_role NOT NULL DEFAULT 'staff'::public.user_role;
    
    COMMENT ON COLUMN public.profiles.role_rbac IS
      'Rol RBAC de seguridad (superadmin/admin/staff). Independiente del rol operativo (role).';
    
    -- Migración de datos: owner legado → admin, resto → staff
    -- Esta es una migración conservadora que puede ajustarse según necesidades
    UPDATE public.profiles 
    SET role_rbac = 'admin'::public.user_role 
    WHERE role = 'owner'::public.user_role 
      AND role_rbac = 'staff'::public.user_role;
  END IF;
END $$;

-- 5. Actualizar función set_rbac_session para soportar los nuevos roles
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
  r := lower(trim(both from coalesce(p_rbac_role, 'staff')));
  
  -- Validar que el rol sea uno de los permitidos
  IF r NOT IN ('superadmin', 'admin', 'staff', 'owner', 'traffic_manager', 'driver', 'cliente', 'developer') THEN
    r := 'staff';
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
  'Fija app.rbac_role y app.assigned_vehiculo_id para políticas RLS. Soporta roles: superadmin, admin, staff, owner, traffic_manager, driver, cliente, developer.';

-- 6. Crear helper function para verificar si un usuario tiene permisos de admin
CREATE OR REPLACE FUNCTION public.is_admin_or_higher()
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
DECLARE
  current_role text;
BEGIN
  current_role := public.app_rbac_role();
  RETURN current_role IN ('superadmin', 'admin', 'owner', 'developer');
END;
$$;

COMMENT ON FUNCTION public.is_admin_or_higher() IS
  'Retorna true si el rol actual tiene permisos de administrador (superadmin, admin, owner, developer)';

-- 7. Actualizar políticas RLS para soportar verificación de admin
-- Ejemplo: política más estricta para audit_logs
DROP POLICY IF EXISTS audit_logs_select_admin_only ON public.audit_logs;
CREATE POLICY audit_logs_select_admin_only ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.is_admin_or_higher()
  );

-- 8. Crear índices para optimizar consultas por rol
CREATE INDEX IF NOT EXISTS idx_usuarios_role_rbac 
  ON public.usuarios (role_rbac);

CREATE INDEX IF NOT EXISTS idx_profiles_role_rbac 
  ON public.profiles (role_rbac);

-- 9. Trigger para audit_logs que capture el rol del usuario
CREATE OR REPLACE FUNCTION public.audit_log_with_role()
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
  v_current_role text;
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

  -- Capturar rol actual para auditoría
  v_current_role := public.app_rbac_role();

  -- Añadir el rol al nuevo registro de auditoría
  v_new := jsonb_set(
    coalesce(v_new, '{}'::jsonb), 
    '{_audit_role}', 
    to_jsonb(v_current_role)
  );

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

COMMENT ON FUNCTION public.audit_log_with_role() IS
  'Trigger de auditoría que captura el rol del usuario en el campo _audit_role de new_data';

-- 10. Información de la migración
DO $$
BEGIN
  RAISE NOTICE 'Migración RBAC completada:';
  RAISE NOTICE '- Enum user_role extendido con: superadmin, admin, staff';
  RAISE NOTICE '- Columna role_rbac añadida a usuarios y profiles';
  RAISE NOTICE '- Función is_admin_or_higher() creada';
  RAISE NOTICE '- Políticas RLS actualizadas para audit_logs';
  RAISE NOTICE '- Índices creados para optimizar consultas por rol';
END $$;


-- ============================================================================
-- [62/71] END FILE: 20260319000101_rbac_admin_staff_extension.sql
-- ============================================================================

-- ============================================================================
-- [63/71] BEGIN FILE: 20260319000103_003_esg_factors.sql
-- ============================================================================

-- 003_esg_factors.sql
-- ESG factors catalog for route-level CO2 estimation.

create table if not exists public.factores_emision (
    id uuid primary key default gen_random_uuid(),
    tipo_vehiculo varchar(120) not null,
    normativa varchar(40) not null,
    factor_co2_km double precision not null,
    created_at timestamptz not null default now()
);

create unique index if not exists ux_factores_emision_tipo_normativa
    on public.factores_emision (tipo_vehiculo, normativa);

insert into public.factores_emision (tipo_vehiculo, normativa, factor_co2_km)
values
    ('Articulado > 40t', 'Euro VI', 750.0),
    ('Rigido 12-24t', 'Euro VI', 540.0),
    ('Furgoneta LCV', 'Euro 6', 190.0)
on conflict (tipo_vehiculo, normativa) do update
set factor_co2_km = excluded.factor_co2_km;


-- ============================================================================
-- [63/71] END FILE: 20260319000103_003_esg_factors.sql
-- ============================================================================

-- ============================================================================
-- [64/71] BEGIN FILE: 20260319000104_004_consolidated_rbac_rls.sql
-- ============================================================================

-- ============================================================================
-- Consolidated RBAC + RLS baseline
-- - Removes migration drift by recreating policies from scratch
-- - Tenant isolation is strictly JWT based:
--     (auth.jwt() ->> 'empresa_id')::uuid = <table>.empresa_id
-- - Role enforcement is JWT based via claim "role"
-- ============================================================================

-- Helper: normalized role from JWT.
CREATE OR REPLACE FUNCTION public.jwt_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT lower(trim(both from coalesce(auth.jwt() ->> 'role', '')));
$$;

COMMENT ON FUNCTION public.jwt_role() IS
  'Normalized RBAC role from JWT claim `role`.';

-- Drop all existing policies for target tables.
DO $$
DECLARE
  _table text;
  _policy text;
BEGIN
  FOREACH _table IN ARRAY ARRAY['portes', 'factores_emision', 'geo_cache', 'profiles']
  LOOP
    IF to_regclass(format('public.%I', _table)) IS NULL THEN
      CONTINUE;
    END IF;

    FOR _policy IN
      SELECT p.policyname
      FROM pg_policies p
      WHERE p.schemaname = 'public'
        AND p.tablename = _table
    LOOP
      EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', _policy, _table);
    END LOOP;
  END LOOP;
END $$;

-- ============================================================================
-- PORTES
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.portes') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.portes FORCE ROW LEVEL SECURITY;

  CREATE POLICY portes_select_consolidated
    ON public.portes
    FOR SELECT
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY portes_insert_consolidated
    ON public.portes
    FOR INSERT
    TO authenticated
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY portes_update_consolidated
    ON public.portes
    FOR UPDATE
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    )
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY portes_delete_consolidated
    ON public.portes
    FOR DELETE
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );
END $$;

-- ============================================================================
-- FACTORES_EMISION
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.factores_emision') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.factores_emision ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.factores_emision FORCE ROW LEVEL SECURITY;

  CREATE POLICY factores_emision_select_consolidated
    ON public.factores_emision
    FOR SELECT
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY factores_emision_write_consolidated
    ON public.factores_emision
    FOR ALL
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    )
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );
END $$;

-- ============================================================================
-- GEO_CACHE
-- Only admin + gestor can read/write tenant cache rows.
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.geo_cache') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.geo_cache ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.geo_cache FORCE ROW LEVEL SECURITY;

  CREATE POLICY geo_cache_select_consolidated
    ON public.geo_cache
    FOR SELECT
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY geo_cache_write_consolidated
    ON public.geo_cache
    FOR ALL
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    )
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );
END $$;

-- ============================================================================
-- PROFILES
-- Users can only read/update their own profile in their JWT tenant.
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.profiles') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;

  CREATE POLICY profiles_select_consolidated
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (
      id = auth.uid()
      AND empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
    );

  CREATE POLICY profiles_update_consolidated
    ON public.profiles
    FOR UPDATE
    TO authenticated
    USING (
      id = auth.uid()
      AND empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
    )
    WITH CHECK (
      id = auth.uid()
      AND empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
    );
END $$;


-- ============================================================================
-- [64/71] END FILE: 20260319000104_004_consolidated_rbac_rls.sql
-- ============================================================================

-- ============================================================================
-- [65/71] BEGIN FILE: 20260319000105_audit_rls_status.sql
-- ============================================================================

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


-- ============================================================================
-- [65/71] END FILE: 20260319000105_audit_rls_status.sql
-- ============================================================================

-- ============================================================================
-- [66/71] BEGIN FILE: 20260319000106_rbac_setup.sql
-- ============================================================================

-- RLS bootstrap for tenant context on Starter/Pro projects.

CREATE OR REPLACE FUNCTION public.app_current_empresa_id()
RETURNS uuid AS $$
  SELECT NULLIF(current_setting('app.current_empresa_id', TRUE), '')::uuid;
$$ LANGUAGE sql STABLE;

DO $$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS facturas_tenant_all ON public.facturas;
    DROP POLICY IF EXISTS facturas_select_rbac ON public.facturas;
    DROP POLICY IF EXISTS facturas_insert_rbac ON public.facturas;
    DROP POLICY IF EXISTS facturas_update_rbac ON public.facturas;
    DROP POLICY IF EXISTS facturas_delete_rbac ON public.facturas;
    CREATE POLICY facturas_tenant_all ON public.facturas
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.transacciones') IS NOT NULL THEN
    ALTER TABLE public.transacciones ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS transacciones_tenant_all ON public.transacciones;
    CREATE POLICY transacciones_tenant_all ON public.transacciones
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.movimientos_bancarios') IS NOT NULL THEN
    ALTER TABLE public.movimientos_bancarios ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS movimientos_bancarios_tenant_all ON public.movimientos_bancarios;
    CREATE POLICY movimientos_bancarios_tenant_all ON public.movimientos_bancarios
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.bank_transactions') IS NOT NULL THEN
    ALTER TABLE public.bank_transactions ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_transactions_tenant_all ON public.bank_transactions;
    CREATE POLICY bank_transactions_tenant_all ON public.bank_transactions
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.audit_logs') IS NOT NULL THEN
    ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS audit_logs_select_admin_only ON public.audit_logs;
    DROP POLICY IF EXISTS audit_logs_select_tenant_admin ON public.audit_logs;
    DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
    CREATE POLICY audit_logs_select_tenant ON public.audit_logs
      FOR SELECT
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;
END
$$;


-- ============================================================================
-- [66/71] END FILE: 20260319000106_rbac_setup.sql
-- ============================================================================

-- ============================================================================
-- [67/71] BEGIN FILE: 20260319000107_verifactu_logic.sql
-- ============================================================================

ALTER TABLE public.facturas DISABLE TRIGGER trg_verifactu_immutable;
DELETE FROM public.facturas WHERE empresa_id = '9189c32e-43d4-4efb-8a65-c7c04d252ef3';
ALTER TABLE public.facturas ENABLE TRIGGER trg_verifactu_immutable;

TRUNCATE public.audit_logs CASCADE;


-- ============================================================================
-- [67/71] END FILE: 20260319000107_verifactu_logic.sql
-- ============================================================================

-- ============================================================================
-- [68/71] BEGIN FILE: 20260414120000_geo_cache_and_portes_coords.sql
-- ============================================================================

-- Global geo cache (Geocoding + Routes API) for cost control. Accessed by backend (service role).
-- Portes: persisted coordinates and road distance (m) for CO₂ reporting and maps.

CREATE TABLE IF NOT EXISTS public.geo_cache (
  route_key TEXT PRIMARY KEY,
  cache_kind TEXT NOT NULL DEFAULT 'route' CHECK (cache_kind IN ('route', 'geocode')),
  origin TEXT NOT NULL,
  destination TEXT NOT NULL DEFAULT '',
  origin_norm TEXT,
  destination_norm TEXT,
  distance_meters INTEGER NOT NULL DEFAULT 0 CHECK (distance_meters >= 0),
  duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_geo_cache_kind_updated
  ON public.geo_cache (cache_kind, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_geo_cache_norm_pair
  ON public.geo_cache (origin_norm, destination_norm)
  WHERE cache_kind = 'route';

COMMENT ON TABLE public.geo_cache IS
  'Caché global de Geocoding y Routes API (distance_meters, duration_seconds); reduce llamadas facturables.';

ALTER TABLE public.geo_cache ENABLE ROW LEVEL SECURITY;

-- Sin datos sensibles: lectura autenticada; escritura reservada a service_role / backend.
DROP POLICY IF EXISTS geo_cache_select_authenticated ON public.geo_cache;
CREATE POLICY geo_cache_select_authenticated
  ON public.geo_cache
  FOR SELECT
  TO authenticated
  USING (true);

-- Portes: coordenadas y distancia real carretera (m).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS lat_origin DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lng_origin DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lat_dest DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lng_dest DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS real_distance_meters DOUBLE PRECISION;

COMMENT ON COLUMN public.portes.real_distance_meters IS
  'Distancia carretera acumulada (m) vía Google Routes API; CO₂ reporting.';


-- ============================================================================
-- [68/71] END FILE: 20260414120000_geo_cache_and_portes_coords.sql
-- ============================================================================

-- ============================================================================
-- [69/71] BEGIN FILE: 20260414130000_esg_co2_module.sql
-- ============================================================================

-- ESG CO2 module aligned with Euro VI fleet standards.

create table if not exists public.estandares_emision_flota (
    id uuid primary key default gen_random_uuid(),
    categoria_vehiculo text not null,
    segmento_mma text not null,
    factor_emision_kg_km numeric(10,6) not null check (factor_emision_kg_km >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (categoria_vehiculo, segmento_mma)
);

insert into public.estandares_emision_flota (categoria_vehiculo, segmento_mma, factor_emision_kg_km)
values
    ('Ligero', '<3.5t', 0.21),
    ('Rígido Pequeño', '3.5t-7.5t', 0.50),
    ('Rígido Grande', '7.5t-16t', 0.68),
    ('Articulado', '>33t', 0.95)
on conflict (categoria_vehiculo, segmento_mma) do update
set
    factor_emision_kg_km = excluded.factor_emision_kg_km,
    updated_at = now();

alter table if exists public.portes
add column if not exists co2_kg numeric(14,6),
add column if not exists factor_emision_aplicado numeric(10,6);


-- ============================================================================
-- [69/71] END FILE: 20260414130000_esg_co2_module.sql
-- ============================================================================

-- ============================================================================
-- [70/71] BEGIN FILE: 20260415130000_audit_security_fixes.sql
-- ============================================================================

-- Supabase security analyzer remediations:
-- 1) Enable and enforce RLS on auth-related tables.
-- 2) Make selected views run with security_invoker.
-- 3) Lock function search_path to public.

-- ---------------------------------------------------------------------------
-- 1) RLS Disabled fixes
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'refresh_tokens'
      AND c.relkind = 'r'
  ) THEN
    EXECUTE 'ALTER TABLE public.refresh_tokens ENABLE ROW LEVEL SECURITY';
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'user_accounts'
      AND c.relkind = 'r'
  ) THEN
    EXECUTE 'ALTER TABLE public.user_accounts ENABLE ROW LEVEL SECURITY';
  END IF;
END
$$;

-- Owner-only access policies (auth.uid() must match user_id).
DROP POLICY IF EXISTS refresh_tokens_owner_only ON public.refresh_tokens;
CREATE POLICY refresh_tokens_owner_only
  ON public.refresh_tokens
  FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS user_accounts_owner_only ON public.user_accounts;
CREATE POLICY user_accounts_owner_only
  ON public.user_accounts
  FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- 2) Security Definer Views fixes
-- ---------------------------------------------------------------------------

ALTER VIEW IF EXISTS public.portes_activos SET (security_invoker = on);
ALTER VIEW IF EXISTS public.vw_esg_emissions_summary SET (security_invoker = on);

-- ---------------------------------------------------------------------------
-- 3) Mutable Search Path fixes
-- ---------------------------------------------------------------------------

ALTER FUNCTION public.app_assigned_vehiculo_id() SET search_path = public;
ALTER FUNCTION public.app_current_cliente_id() SET search_path = public;
ALTER FUNCTION public.app_current_empresa_id() SET search_path = public;
ALTER FUNCTION public.app_current_user_role() SET search_path = public;
ALTER FUNCTION public.app_rbac_role() SET search_path = public;
ALTER FUNCTION public.check_empresa_id_lock() SET search_path = public;
ALTER FUNCTION public.check_fiscal_immutability() SET search_path = public;
ALTER FUNCTION public.check_limite_starter() SET search_path = public;


-- ============================================================================
-- [70/71] END FILE: 20260415130000_audit_security_fixes.sql
-- ============================================================================

-- ============================================================================
-- [71/71] BEGIN FILE: 20260614000000_auth_autonomous_onboarding.sql
-- ============================================================================

-- Onboarding autónomo inicial: crea empresa + enlaza perfil autenticado.
-- Seguridad:
--   - Solo permite el "primer enlace" cuando profiles.empresa_id IS NULL.
--   - El cambio posterior de empresa_id sigue bloqueado por trigger de seguridad.

CREATE OR REPLACE FUNCTION public.auth_onboarding_setup(
  p_company_name text,
  p_cif text,
  p_address text,
  p_initial_fleet_type text,
  p_target_margin_pct numeric DEFAULT NULL
)
RETURNS TABLE (empresa_id uuid, profile_id uuid, role text)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
  v_uid uuid;
  v_empresa_id uuid;
BEGIN
  v_uid := auth.uid();
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'auth_uid_missing';
  END IF;

  PERFORM 1
  FROM public.profiles p
  WHERE p.id = v_uid
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'profile_not_found';
  END IF;

  PERFORM 1
  FROM public.profiles p
  WHERE p.id = v_uid
    AND p.empresa_id IS NOT NULL;

  IF FOUND THEN
    RAISE EXCEPTION 'already_onboarded';
  END IF;

  INSERT INTO public.empresas (
    nif,
    nombre_legal,
    nombre_comercial,
    direccion,
    plan,
    activa
  )
  VALUES (
    trim(coalesce(p_cif, '')),
    trim(coalesce(p_company_name, '')),
    trim(coalesce(p_company_name, '')),
    trim(coalesce(p_address, '')),
    'starter',
    true
  )
  RETURNING id INTO v_empresa_id;

  UPDATE public.profiles
  SET
    empresa_id = v_empresa_id,
    role = 'admin'::public.user_role,
    rol = 'admin'
  WHERE id = v_uid
    AND empresa_id IS NULL;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'already_onboarded';
  END IF;

  IF to_regclass('public.factores_emision') IS NOT NULL THEN
    -- Semilla opcional: placeholder para estrategias de factores por empresa.
    PERFORM 1;
  END IF;

  RETURN QUERY
  SELECT v_empresa_id, v_uid, 'admin'::text;
END;
$$;

GRANT EXECUTE ON FUNCTION public.auth_onboarding_setup(text, text, text, text, numeric) TO authenticated;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    DROP POLICY IF EXISTS profiles_update_authenticated ON public.profiles;
    CREATE POLICY profiles_update_authenticated ON public.profiles
      FOR UPDATE
      TO authenticated
      USING (auth.uid() = id AND empresa_id IS NULL)
      WITH CHECK (auth.uid() = id AND empresa_id IS NOT NULL);
  END IF;
END $$;

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

  -- Primer onboarding del propio usuario autenticado.
  IF OLD.empresa_id IS NULL
     AND NEW.empresa_id IS NOT NULL
     AND auth.uid() = OLD.id THEN
    RETURN NEW;
  END IF;

  IF current_setting('role', true) = 'service_role' THEN
    RETURN NEW;
  END IF;

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


-- ============================================================================
-- [71/71] END FILE: 20260614000000_auth_autonomous_onboarding.sql
-- ============================================================================
