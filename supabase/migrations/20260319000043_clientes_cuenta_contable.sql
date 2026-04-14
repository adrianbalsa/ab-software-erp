-- Cuenta contable PGC opcional por cliente (exportación a gestoría).
ALTER TABLE public.clientes ADD COLUMN IF NOT EXISTS cuenta_contable text;

COMMENT ON COLUMN public.clientes.cuenta_contable IS
  'Cuenta 430… si se informa; si NULL, la exportación genera 430 + sufijo determinista desde id.';
