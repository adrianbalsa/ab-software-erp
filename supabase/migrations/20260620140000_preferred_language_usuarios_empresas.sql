-- Preferred UI/document language (ISO-style codes, typically es | en).
ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS preferred_language character varying(5) NOT NULL DEFAULT 'es';

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS preferred_language character varying(5) NOT NULL DEFAULT 'es';

COMMENT ON COLUMN public.usuarios.preferred_language IS
  'User preference for PDFs, emails and audit copy (e.g. es, en).';

COMMENT ON COLUMN public.empresas.preferred_language IS
  'Company default language for generated documents when user preference is absent.';
