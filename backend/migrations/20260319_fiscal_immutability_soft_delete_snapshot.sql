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
