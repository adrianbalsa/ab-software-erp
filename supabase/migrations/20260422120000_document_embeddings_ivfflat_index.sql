-- Índice IVFFlat para búsqueda aproximada por similitud coseno en ``document_embeddings``.
-- Con pocos registros el planificador puede seguir usando sequential scan; a partir de ~1k–10k
-- filas suele compensar. Ajustar ``lists`` (p. ej. 100) si el volumen crece mucho.

CREATE INDEX IF NOT EXISTS document_embeddings_embedding_ivfflat_idx
  ON public.document_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

COMMENT ON INDEX public.document_embeddings_embedding_ivfflat_idx IS
  'IVFFlat cosine: acelera match_document_embeddings en tenants con volumen. Reindexar/analizar tras cargas masivas.';
