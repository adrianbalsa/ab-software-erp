-- ESG Fase 2.5: snapshot mensual inmutable + calidad de km + bloqueo de mutación CO2/distancia
-- tras cierre (WORM operativo a nivel porte para campos ESG).

-- ---------------------------------------------------------------------------
-- portes: origen de datos de km (auditoría) + bandera de cierre de periodo
-- ---------------------------------------------------------------------------
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS esg_km_source text,
  ADD COLUMN IF NOT EXISTS esg_data_locked boolean NOT NULL DEFAULT false;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'portes_esg_km_source_check'
  ) THEN
    ALTER TABLE public.portes
      ADD CONSTRAINT portes_esg_km_source_check CHECK (
        esg_km_source IS NULL
        OR esg_km_source IN (
          'route_api_meters',
          'recorded_road_km',
          'telemetry',
          'estimated'
        )
      );
  END IF;
END $$;

COMMENT ON COLUMN public.portes.esg_km_source IS
  'Procedencia del km usado para reporting ESG: route_api_meters (Routes API m), recorded_road_km (km persistido operativo), telemetry (GPS futuro), estimated (solo km_estimados).';
COMMENT ON COLUMN public.portes.esg_data_locked IS
  'True si el porte quedó incluido en un cierre ESG mensual: no se permiten cambios en CO2 ni distancias de referencia.';

-- ---------------------------------------------------------------------------
-- esg_period_snapshots: un registro append-only por empresa y mes calendario
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.esg_period_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  period_year smallint NOT NULL CHECK (period_year >= 2000 AND period_year <= 2100),
  period_month smallint NOT NULL CHECK (period_month >= 1 AND period_month <= 12),
  closed_at timestamptz NOT NULL DEFAULT now(),
  closed_by uuid,
  num_portes_facturados integer NOT NULL DEFAULT 0 CHECK (num_portes_facturados >= 0),
  total_co2_kg numeric(20, 6) NOT NULL DEFAULT 0,
  total_km_activity numeric(20, 6) NOT NULL DEFAULT 0 CHECK (total_km_activity >= 0),
  pct_km_route_api_meters numeric(9, 6) NOT NULL DEFAULT 0 CHECK (pct_km_route_api_meters >= 0 AND pct_km_route_api_meters <= 100),
  pct_km_recorded_road_km numeric(9, 6) NOT NULL DEFAULT 0 CHECK (pct_km_recorded_road_km >= 0 AND pct_km_recorded_road_km <= 100),
  pct_km_telemetry numeric(9, 6) NOT NULL DEFAULT 0 CHECK (pct_km_telemetry >= 0 AND pct_km_telemetry <= 100),
  pct_km_estimated numeric(9, 6) NOT NULL DEFAULT 0 CHECK (pct_km_estimated >= 0 AND pct_km_estimated <= 100),
  content_sha256 text NOT NULL,
  snapshot_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_esg_period_snapshots_empresa_period
  ON public.esg_period_snapshots (empresa_id, period_year, period_month);

CREATE INDEX IF NOT EXISTS idx_esg_period_snapshots_empresa_closed
  ON public.esg_period_snapshots (empresa_id, closed_at DESC);

COMMENT ON TABLE public.esg_period_snapshots IS
  'Cierre mensual ESG (append-only): totales, KPI cobertura de km por fuente y huella SHA-256 del payload canónico.';

-- Inmutabilidad tabla snapshot (no UPDATE / DELETE)
CREATE OR REPLACE FUNCTION public._esg_period_snapshots_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    RAISE EXCEPTION 'esg_period_snapshots es inmutable (operación % no permitida)', TG_OP;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_esg_period_snapshots_immutable ON public.esg_period_snapshots;
CREATE TRIGGER trg_esg_period_snapshots_immutable
  BEFORE UPDATE OR DELETE ON public.esg_period_snapshots
  FOR EACH ROW
  EXECUTE PROCEDURE public._esg_period_snapshots_immutable();

-- Bloqueo CO2 / distancia en portes cuando esg_data_locked = true
CREATE OR REPLACE FUNCTION public._portes_block_esg_mutation_when_locked()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP <> 'UPDATE' THEN
    RETURN NEW;
  END IF;
  IF COALESCE(OLD.esg_data_locked, false) THEN
    IF NEW.co2_emitido IS DISTINCT FROM OLD.co2_emitido
       OR NEW.co2_kg IS DISTINCT FROM OLD.co2_kg
       OR NEW.factor_emision_aplicado IS DISTINCT FROM OLD.factor_emision_aplicado
       OR NEW.real_distance_meters IS DISTINCT FROM OLD.real_distance_meters
       OR NEW.km_estimados IS DISTINCT FROM OLD.km_estimados
       OR NEW.esg_km_source IS DISTINCT FROM OLD.esg_km_source
    THEN
      RAISE EXCEPTION 'Porte ESG bloqueado (cierre de periodo): no se permiten cambios en CO2, factor o distancia de referencia';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_portes_block_esg_when_locked ON public.portes;
CREATE TRIGGER trg_portes_block_esg_when_locked
  BEFORE UPDATE ON public.portes
  FOR EACH ROW
  EXECUTE PROCEDURE public._portes_block_esg_mutation_when_locked();

-- RLS (mismo patrón que esg_certificate_documents)
ALTER TABLE public.esg_period_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS esg_period_snapshots_select ON public.esg_period_snapshots;
CREATE POLICY esg_period_snapshots_select ON public.esg_period_snapshots
  FOR SELECT TO authenticated
  USING (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'gestor', 'admin')
  );

DROP POLICY IF EXISTS esg_period_snapshots_insert ON public.esg_period_snapshots;
CREATE POLICY esg_period_snapshots_insert ON public.esg_period_snapshots
  FOR INSERT TO authenticated
  WITH CHECK (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'admin')
  );

GRANT SELECT, INSERT ON public.esg_period_snapshots TO authenticated;
GRANT SELECT, INSERT ON public.esg_period_snapshots TO service_role;
