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
