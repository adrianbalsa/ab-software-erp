-- Onboarding B2B (portal cliente): base de riesgo + aceptación legal explícita.
-- Compatibilidad: todos los cambios son idempotentes.

-- 1) Extiende el enum de auditoría para eventos de onboarding.
ALTER TYPE public.audit_action ADD VALUE IF NOT EXISTS 'INVITE_SENT';
ALTER TYPE public.audit_action ADD VALUE IF NOT EXISTS 'RISK_ACCEPTED';

-- 2) Señales de riesgo en clientes (MVP).
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS limite_credito numeric(12,2) NOT NULL DEFAULT 3000,
  ADD COLUMN IF NOT EXISTS has_payment_history boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.clientes.limite_credito IS
  'Límite de crédito definido por operación/comercial para evaluar riesgo y exposición.';
COMMENT ON COLUMN public.clientes.has_payment_history IS
  'TRUE cuando existe historial de pagos operativo verificable para el cliente.';

-- 3) Evidencia de aceptación legal en onboarding (portal).
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS riesgo_aceptado boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS riesgo_aceptado_at timestamptz;

COMMENT ON COLUMN public.clientes.riesgo_aceptado IS
  'Aceptación explícita del cliente de la evaluación de riesgo y cobro automático SEPA.';
COMMENT ON COLUMN public.clientes.riesgo_aceptado_at IS
  'Timestamp UTC de aceptación legal en el portal cliente.';

-- Índice parcial para panel operativo (pendientes de aceptación).
CREATE INDEX IF NOT EXISTS idx_clientes_riesgo_aceptado_false
  ON public.clientes (empresa_id, created_at DESC)
  WHERE riesgo_aceptado = false;

