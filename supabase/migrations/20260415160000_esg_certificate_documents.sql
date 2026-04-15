-- Certificados ESG generados en servidor: huella SHA-256 y trazabilidad M&A.
-- RLS con public.app_current_empresa_id() y roles operativos.

CREATE TABLE IF NOT EXISTS public.esg_certificate_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  certificate_id text NOT NULL,
  subject_type text NOT NULL CHECK (subject_type IN ('porte', 'factura')),
  subject_id text NOT NULL,
  sha256_pdf text NOT NULL,
  content_fingerprint_sha256 text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_esg_certificate_documents_cert_id
  ON public.esg_certificate_documents (certificate_id);

CREATE INDEX IF NOT EXISTS idx_esg_certificate_documents_empresa_created
  ON public.esg_certificate_documents (empresa_id, created_at DESC);

COMMENT ON TABLE public.esg_certificate_documents IS
  'Registro inmutable de certificados ESG emitidos por la API (hash PDF + fingerprint de contenido).';

ALTER TABLE public.esg_certificate_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS esg_certificate_documents_select ON public.esg_certificate_documents;
CREATE POLICY esg_certificate_documents_select ON public.esg_certificate_documents
  FOR SELECT TO authenticated
  USING (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'gestor', 'admin')
  );

DROP POLICY IF EXISTS esg_certificate_documents_insert ON public.esg_certificate_documents;
CREATE POLICY esg_certificate_documents_insert ON public.esg_certificate_documents
  FOR INSERT TO authenticated
  WITH CHECK (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'gestor', 'admin')
  );

GRANT SELECT, INSERT ON public.esg_certificate_documents TO authenticated;
GRANT SELECT, INSERT ON public.esg_certificate_documents TO service_role;
