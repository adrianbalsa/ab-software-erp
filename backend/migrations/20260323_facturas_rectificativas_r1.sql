-- Rectificativas VeriFactu R1 [cite: 2026-03-22]
-- Vínculo a factura original sellada + motivo (texto libre para expediente).

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS factura_rectificada_id UUID REFERENCES public.facturas (id);

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS motivo_rectificacion TEXT;

COMMENT ON COLUMN public.facturas.factura_rectificada_id IS
  'Factura F1 (u original) que corrige esta R1; NULL en facturas normales.';
COMMENT ON COLUMN public.facturas.motivo_rectificacion IS
  'Motivo de la rectificación (VeriFactu / trazabilidad).';

CREATE INDEX IF NOT EXISTS idx_facturas_rectificada_id
  ON public.facturas (factura_rectificada_id)
  WHERE factura_rectificada_id IS NOT NULL;
