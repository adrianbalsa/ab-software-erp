-- Dedupe de webhooks por id de evento del proveedor (Stripe, GoCardless).

BEGIN;

ALTER TABLE public.webhook_events
  ADD COLUMN IF NOT EXISTS external_event_id text;

COMMENT ON COLUMN public.webhook_events.external_event_id IS
  'Id único del evento en el proveedor (p. ej. evt_xxx Stripe, EVxxx GoCardless). NULL = sin dedupe.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_events_provider_external_event_id
  ON public.webhook_events (provider, external_event_id)
  WHERE external_event_id IS NOT NULL AND length(btrim(external_event_id)) > 0;

COMMIT;
