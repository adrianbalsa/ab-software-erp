-- Cost caps mensuales por tenant para servicios de coste externo (Maps/OCR/IA).

CREATE TABLE IF NOT EXISTS public.tenant_monthly_usage (
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  period_yyyymm TEXT NOT NULL CHECK (period_yyyymm ~ '^[0-9]{4}-[0-9]{2}$'),
  meter TEXT NOT NULL CHECK (meter IN ('maps_calls_month', 'ocr_pages_month', 'ai_tokens_month')),
  used_units INTEGER NOT NULL DEFAULT 0 CHECK (used_units >= 0),
  limit_units INTEGER NOT NULL CHECK (limit_units >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (empresa_id, period_yyyymm, meter)
);

CREATE INDEX IF NOT EXISTS idx_tenant_monthly_usage_period
  ON public.tenant_monthly_usage (period_yyyymm, meter);

COMMENT ON TABLE public.tenant_monthly_usage IS
  'Consumo mensual persistente por tenant para hard caps de servicios externos (Maps calls/OCR pages/AI tokens).';

ALTER TABLE public.tenant_monthly_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_monthly_usage_tenant_all ON public.tenant_monthly_usage;
CREATE POLICY tenant_monthly_usage_tenant_all
  ON public.tenant_monthly_usage
  FOR ALL
  TO authenticated
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

CREATE OR REPLACE FUNCTION public.consume_tenant_monthly_quota(
  p_empresa_id UUID,
  p_period_yyyymm TEXT,
  p_meter TEXT,
  p_units INTEGER,
  p_limit_units INTEGER
)
RETURNS TABLE (
  allowed BOOLEAN,
  empresa_id UUID,
  period_yyyymm TEXT,
  meter TEXT,
  used_units INTEGER,
  limit_units INTEGER
)
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
  v_current_empresa TEXT;
BEGIN
  v_current_empresa := public.app_current_empresa_id()::text;
  IF v_current_empresa IS NULL OR p_empresa_id::text <> v_current_empresa THEN
    RAISE EXCEPTION 'tenant context mismatch' USING ERRCODE = '42501';
  END IF;
  IF p_units IS NULL OR p_units <= 0 THEN
    RAISE EXCEPTION 'p_units must be positive' USING ERRCODE = '22023';
  END IF;
  IF p_limit_units IS NULL OR p_limit_units < 0 THEN
    RAISE EXCEPTION 'p_limit_units must be non-negative' USING ERRCODE = '22023';
  END IF;
  IF p_meter NOT IN ('maps_calls_month', 'ocr_pages_month', 'ai_tokens_month') THEN
    RAISE EXCEPTION 'invalid meter' USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
  WITH attempted AS (
    INSERT INTO public.tenant_monthly_usage (
      empresa_id,
      period_yyyymm,
      meter,
      used_units,
      limit_units,
      updated_at
    )
    SELECT
      p_empresa_id,
      p_period_yyyymm,
      p_meter,
      p_units,
      p_limit_units,
      now()
    WHERE p_units <= p_limit_units
    ON CONFLICT (empresa_id, period_yyyymm, meter)
    DO UPDATE
      SET used_units = public.tenant_monthly_usage.used_units + EXCLUDED.used_units,
          limit_units = EXCLUDED.limit_units,
          updated_at = now()
      WHERE public.tenant_monthly_usage.used_units + EXCLUDED.used_units <= EXCLUDED.limit_units
    RETURNING
      true AS allowed,
      public.tenant_monthly_usage.empresa_id,
      public.tenant_monthly_usage.period_yyyymm,
      public.tenant_monthly_usage.meter,
      public.tenant_monthly_usage.used_units,
      public.tenant_monthly_usage.limit_units
  ),
  current_row AS (
    SELECT
      false AS allowed,
      t.empresa_id,
      t.period_yyyymm,
      t.meter,
      t.used_units,
      t.limit_units
    FROM public.tenant_monthly_usage AS t
    WHERE t.empresa_id = p_empresa_id
      AND t.period_yyyymm = p_period_yyyymm
      AND t.meter = p_meter
      AND NOT EXISTS (SELECT 1 FROM attempted)
    UNION ALL
    SELECT
      false AS allowed,
      p_empresa_id AS empresa_id,
      p_period_yyyymm AS period_yyyymm,
      p_meter AS meter,
      0 AS used_units,
      p_limit_units AS limit_units
    WHERE NOT EXISTS (SELECT 1 FROM attempted)
      AND NOT EXISTS (
        SELECT 1
        FROM public.tenant_monthly_usage AS t
        WHERE t.empresa_id = p_empresa_id
          AND t.period_yyyymm = p_period_yyyymm
          AND t.meter = p_meter
      )
  )
  SELECT * FROM attempted
  UNION ALL
  SELECT * FROM current_row
  LIMIT 1;
END;
$$;

COMMENT ON FUNCTION public.consume_tenant_monthly_quota(UUID, TEXT, TEXT, INTEGER, INTEGER) IS
  'Reserva consumo mensual de forma atómica. Devuelve allowed=false si el hard cap se supera.';

GRANT EXECUTE ON FUNCTION public.consume_tenant_monthly_quota(UUID, TEXT, TEXT, INTEGER, INTEGER)
  TO authenticated;
