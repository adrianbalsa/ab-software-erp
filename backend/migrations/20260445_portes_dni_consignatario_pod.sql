-- DNI/NIE opcional del consignatario (POD).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS dni_consignatario text;

COMMENT ON COLUMN public.portes.dni_consignatario IS 'DNI/NIE del consignatario (opcional, entrega POD).';
