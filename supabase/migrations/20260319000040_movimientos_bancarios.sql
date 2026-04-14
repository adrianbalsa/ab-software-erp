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
