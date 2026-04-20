-- E2E Banking: columnas pedidas para cuentas (token cifrado por app) y estado de conciliación explícito en movimientos.
-- RLS: sin cambios — ambas tablas siguen ancladas a empresa_id vía app_current_empresa_id().

ALTER TABLE public.bank_accounts
  ADD COLUMN IF NOT EXISTS access_token_encrypted TEXT;

COMMENT ON COLUMN public.bank_accounts.access_token_encrypted IS
  'Token de acceso GoCardless de corta duración cifrado (Fernet) opcional por cuenta; la app puede dejarlo NULL y usar empresa_banco_sync.';

ALTER TABLE public.bank_transactions
  ADD COLUMN IF NOT EXISTS status_reconciled TEXT NOT NULL DEFAULT 'pending';

COMMENT ON COLUMN public.bank_transactions.status_reconciled IS
  'pending | reconciled — espejo lógico de reconciled; actualizado por la app al confirmar match.';

UPDATE public.bank_transactions
SET status_reconciled = 'reconciled'
WHERE reconciled IS TRUE AND (status_reconciled IS DISTINCT FROM 'reconciled');

UPDATE public.bank_transactions
SET status_reconciled = 'pending'
WHERE reconciled IS NOT TRUE AND (status_reconciled IS DISTINCT FROM 'pending');
