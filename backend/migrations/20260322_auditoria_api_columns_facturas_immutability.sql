-- Producción VeriFactu: columnas usadas por la API y regla de inmutabilidad básica.
-- Ejecutar en Supabase SQL Editor (producción) tras las migraciones previas.

-- 1) Auditoría: columnas que inserta `AuditoriaService` / `VerifactuService.registrar_evento`
ALTER TABLE public.auditoria
  ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ;

COMMENT ON COLUMN public.auditoria.timestamp IS 'Duplicado opcional de fecha (ISO desde API)';

-- Si `cambios` es JSONB y la API envía texto, Postgres suele castear; si prefieres TEXT:
-- ALTER TABLE public.auditoria ALTER COLUMN cambios TYPE TEXT USING cambios::text;

-- 2) Inmutabilidad: no alterar huella/número de factura VeriFactu si el registro está bloqueado
CREATE OR REPLACE FUNCTION public.prevent_locked_factura_verifactu_mutate()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF COALESCE(OLD.bloqueado, FALSE) IS TRUE THEN
    IF NEW.hash_registro IS DISTINCT FROM OLD.hash_registro
       OR NEW.hash_factura IS DISTINCT FROM OLD.hash_factura
       OR NEW.num_factura IS DISTINCT FROM OLD.num_factura
       OR NEW.numero_factura IS DISTINCT FROM OLD.numero_factura
       OR NEW.numero_secuencial IS DISTINCT FROM OLD.numero_secuencial
       OR NEW.hash_anterior IS DISTINCT FROM OLD.hash_anterior
    THEN
      RAISE EXCEPTION 'Factura bloqueada (VeriFactu): no se permiten cambios en huella o numeración';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_verifactu_locked ON public.facturas;
CREATE TRIGGER trg_facturas_verifactu_locked
  BEFORE UPDATE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.prevent_locked_factura_verifactu_mutate();
