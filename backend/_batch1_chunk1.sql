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
      WHERE 