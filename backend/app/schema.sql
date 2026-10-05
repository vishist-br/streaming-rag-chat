-- Applied on startup; every statement is idempotent.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        TEXT NOT NULL UNIQUE,
    content_hash    TEXT NOT NULL,          -- sha256 of the raw file bytes
    embedding_model TEXT NOT NULL,          -- vectors from different models are not comparable
    num_chunks      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id  UUID NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    page         INTEGER,                   -- 1-based, PDFs only
    section      TEXT NOT NULL DEFAULT '',  -- heading path, e.g. "Battery > Charging"
    content      TEXT NOT NULL,
    content_hash TEXT NOT NULL,             -- sha256 of section + content, used to reuse embeddings
    token_count  INTEGER NOT NULL,
    embedding    vector(768) NOT NULL,
    -- Kept in sync by Postgres itself, so ingestion code cannot forget to update it.
    tsv          tsvector GENERATED ALWAYS AS (
                     to_tsvector('english', section || ' ' || content)
                 ) STORED,
    UNIQUE (document_id, chunk_index)
);

-- Approximate nearest neighbour index for cosine distance (the <=> operator).
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Inverted index for full-text search.
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
