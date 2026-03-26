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

