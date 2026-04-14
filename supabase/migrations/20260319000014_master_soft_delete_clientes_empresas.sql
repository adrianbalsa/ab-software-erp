-- D2/D3: columnas de borrado lógico en maestras (idempotente).
-- Ejecutar en Supabase si las tablas aún no tienen `deleted_at`.

ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

COMMENT ON COLUMN public.clientes.deleted_at IS 'NULL = activo; IS NOT NULL = archivado (UI oculta)';
COMMENT ON COLUMN public.empresas.deleted_at IS 'NULL = activo; IS NOT NULL = empresa archivada (admin)';
