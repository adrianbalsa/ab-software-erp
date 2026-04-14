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
