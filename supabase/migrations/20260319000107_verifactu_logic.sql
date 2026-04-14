ALTER TABLE public.facturas DISABLE TRIGGER trg_verifactu_immutable;
DELETE FROM public.facturas WHERE empresa_id = '9189c32e-43d4-4efb-8a65-c7c04d252ef3';
ALTER TABLE public.facturas ENABLE TRIGGER trg_verifactu_immutable;

TRUNCATE public.audit_logs CASCADE;
