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

