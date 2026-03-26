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