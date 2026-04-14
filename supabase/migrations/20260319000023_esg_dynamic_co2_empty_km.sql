-- ESG phase completion: dynamic factors + empty kilometers metadata.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS engine_class varchar(32) NOT NULL DEFAULT 'EURO_VI',
  ADD COLUMN IF NOT EXISTS fuel_type varchar(32) NOT NULL DEFAULT 'DIESEL';

COMMENT ON COLUMN public.flota.engine_class IS
  'Clase de motor para factores dinámicos ESG (ej. EURO_VI, EURO_V, EURO_IV, EV).';
COMMENT ON COLUMN public.flota.fuel_type IS
  'Tipo de combustible para factores dinámicos ESG (ej. DIESEL, ELECTRIC, HIBRIDO, GASOLINA).';

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS km_vacio numeric(12,3) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS subcontratado boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.portes.km_vacio IS
  'Kilómetros recorridos en vacío (sin carga) para cálculo dinámico de CO2.';
COMMENT ON COLUMN public.portes.subcontratado IS
  'true si el porte se ejecuta por tercero (Scope 3); false para flota propia (Scope 1).';
