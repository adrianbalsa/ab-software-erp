-- CMR: nombre del conductor (opcional; si NULL, el PDF deja la casilla en blanco).
ALTER TABLE public.portes ADD COLUMN IF NOT EXISTS conductor_nombre text;

COMMENT ON COLUMN public.portes.conductor_nombre IS
  'Nombre del conductor para carta de porte (CMR); opcional.';
