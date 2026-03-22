-- XML de alta VeriFactu (registro exportable / trazabilidad) persistido con la factura.
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS xml_verifactu TEXT;

COMMENT ON COLUMN public.facturas.xml_verifactu IS
  'XML UTF-8 de registro VeriFactu (Cabecera, RegistroFactura, Desglose) generado al sellar el hash';
