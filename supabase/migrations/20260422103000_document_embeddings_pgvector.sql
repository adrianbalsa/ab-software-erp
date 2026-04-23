-- Vampire Radar / Economic Advisor: embeddings para RAG (pgvector).
-- Dimensión 1536: OpenAI text-embedding-3-small (pipeline unificado).
-- Para embeddings 768 (p. ej. Gemini) añadir columna o tabla aparte en el futuro.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.document_embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  content text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1536) NOT NULL,
  source_sha256 text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_embeddings_empresa_created_idx
  ON public.document_embeddings (empresa_id, created_at DESC);

CREATE INDEX IF NOT EXISTS document_embeddings_source_sha_idx
  ON public.document_embeddings (empresa_id, source_sha256)
  WHERE source_sha256 IS NOT NULL;

-- Índice ANN (ivfflat/hnsw): crear en producción cuando haya volumen suficiente para entrenar listas.
COMMENT ON TABLE public.document_embeddings IS
  'Texto + embedding por documento OCR (Vampire Radar) para consultas RAG (Economic Advisor).';
COMMENT ON COLUMN public.document_embeddings.embedding IS
  'Vector 1536d (OpenAI text-embedding-3-small).';

ALTER TABLE public.document_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_embeddings FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS document_embeddings_tenant_all ON public.document_embeddings;
CREATE POLICY document_embeddings_tenant_all ON public.document_embeddings
  FOR ALL
  TO authenticated
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- Búsqueda por similitud coseno (operador <=> = distancia coseno en pgvector).
CREATE OR REPLACE FUNCTION public.match_document_embeddings(
  p_query_embedding vector(1536),
  p_match_count integer DEFAULT 8
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  similarity double precision
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
  SELECT
    de.id,
    de.content,
    de.metadata,
    (1 - (de.embedding <=> p_query_embedding))::double precision AS similarity
  FROM public.document_embeddings de
  WHERE de.empresa_id::text = public.app_current_empresa_id()::text
  ORDER BY de.embedding <=> p_query_embedding
  LIMIT LEAST(COALESCE(p_match_count, 8), 50);
$$;

COMMENT ON FUNCTION public.match_document_embeddings(vector(1536), integer) IS
  'Recupera fragmentos del tenant actual ordenados por similitud coseno (mayor similarity = más relevante).';

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.document_embeddings TO authenticated;
GRANT ALL ON TABLE public.document_embeddings TO service_role;

GRANT EXECUTE ON FUNCTION public.match_document_embeddings(vector(1536), integer)
  TO authenticated, service_role;
