-- ESG certificados audit-ready: código QR público, SHA-256 explícito del PDF y estado de verificación.

ALTER TABLE public.esg_certificate_documents
  ADD COLUMN IF NOT EXISTS verification_code uuid,
  ADD COLUMN IF NOT EXISTS verification_status text,
  ADD COLUMN IF NOT EXISTS certificate_content_sha256 text;

UPDATE public.esg_certificate_documents
SET verification_code = gen_random_uuid()
WHERE verification_code IS NULL;

UPDATE public.esg_certificate_documents
SET verification_status = 'self_certified'
WHERE verification_status IS NULL OR trim(verification_status) = '';

UPDATE public.esg_certificate_documents
SET certificate_content_sha256 = sha256_pdf
WHERE certificate_content_sha256 IS NULL AND sha256_pdf IS NOT NULL;

ALTER TABLE public.esg_certificate_documents
  ALTER COLUMN verification_code SET NOT NULL;

ALTER TABLE public.esg_certificate_documents
  ALTER COLUMN verification_status SET NOT NULL;

ALTER TABLE public.esg_certificate_documents
  ALTER COLUMN verification_status SET DEFAULT 'self_certified';

ALTER TABLE public.esg_certificate_documents
  ALTER COLUMN certificate_content_sha256 SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_esg_certificate_documents_verification_code
  ON public.esg_certificate_documents (verification_code);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'esg_certificate_documents_verification_status_check'
  ) THEN
    ALTER TABLE public.esg_certificate_documents
      ADD CONSTRAINT esg_certificate_documents_verification_status_check
      CHECK (
        verification_status IN (
          'self_certified',
          'pending_external_audit',
          'externally_verified'
        )
      );
  END IF;
END $$;

COMMENT ON COLUMN public.esg_certificate_documents.verification_code IS
  'UUID público: QR y GET /v1/public/verify-esg/{code} (lectura API con service role).';
COMMENT ON COLUMN public.esg_certificate_documents.verification_status IS
  'self_certified | pending_external_audit (Enterprise + solicitud) | externally_verified.';
COMMENT ON COLUMN public.esg_certificate_documents.certificate_content_sha256 IS
  'SHA-256 (hex) del PDF emitido; cotejable por terceros con el fichero recibido.';

CREATE OR REPLACE VIEW public.esg_certificates AS
SELECT
  id,
  empresa_id,
  certificate_id,
  subject_type,
  subject_id,
  certificate_content_sha256,
  content_fingerprint_sha256,
  verification_code,
  verification_status,
  metadata,
  created_at,
  created_by,
  sha256_pdf
FROM public.esg_certificate_documents;

COMMENT ON VIEW public.esg_certificates IS
  'Vista Due Diligence (alias de esg_certificate_documents) para informes M&A / auditoría.';
