"""Ingestion: parse -> chunk -> embed in batches -> store.

Idempotent at two levels:
- same file bytes (document hash)  -> nothing happens;
- edited file                       -> only chunks whose hash changed are re-embedded.
"""

import hashlib

from app.config import Settings
from app.db import Pool, fetch_all, fetch_one, to_pgvector
from app.ingestion.chunking import chunk_blocks
from app.ingestion.parsers import parse_document
from app.models import IngestResult
from app.providers.base import Provider


class EmptyDocumentError(ValueError):
    pass


async def ingest_document(
    pool: Pool, provider: Provider, settings: Settings, filename: str, data: bytes
) -> IngestResult:
    document_hash = hashlib.sha256(data).hexdigest()
    existing = await fetch_one(
        pool,
        "SELECT id, content_hash, embedding_model, num_chunks FROM documents WHERE filename = %s",
        (filename,),
    )
    same_model = existing is not None and existing["embedding_model"] == provider.embedding_id
    if existing and same_model and existing["content_hash"] == document_hash:
        return IngestResult(
            document_id=existing["id"],
            filename=filename,
            status="unchanged",
            num_chunks=existing["num_chunks"],
            embedded_chunks=0,
            reused_chunks=existing["num_chunks"],
            embedding_tokens=0,
        )

    blocks = parse_document(filename, data)
    chunks = chunk_blocks(blocks, settings.chunk_target_tokens, settings.chunk_overlap_tokens)
    if not chunks:
        raise EmptyDocumentError(f"no text could be extracted from '{filename}'")

    # Embeddings we already paid for, keyed by chunk hash. Kept as pgvector text literals.
    known: dict[str, str] = {}
    if existing and same_model:
        rows = await fetch_all(
            pool,
            "SELECT content_hash, embedding::text AS embedding FROM chunks WHERE document_id = %s",
            (existing["id"],),
        )
        known = {row["content_hash"]: row["embedding"] for row in rows}

    to_embed = [c for c in chunks if c.content_hash not in known]
    embedding_tokens = 0
    for start in range(0, len(to_embed), settings.embed_batch_size):
        batch = to_embed[start : start + settings.embed_batch_size]
        result = await provider.embed([c.embedding_text for c in batch])
        embedding_tokens += result.usage.input_tokens
        for chunk, vector in zip(batch, result.vectors, strict=True):
            known[chunk.content_hash] = to_pgvector(vector)

    # One transaction: readers see either the old version or the new one, never a mix.
    async with pool.connection() as conn, conn.transaction():
        cursor = await conn.execute(
            """
            INSERT INTO documents (filename, content_hash, embedding_model, num_chunks)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (filename) DO UPDATE SET
                content_hash = EXCLUDED.content_hash,
                embedding_model = EXCLUDED.embedding_model,
                num_chunks = EXCLUDED.num_chunks,
                updated_at = now()
            RETURNING id
            """,
            (filename, document_hash, provider.embedding_id, len(chunks)),
        )
        row = await cursor.fetchone()
        assert row is not None
        document_id = row[0]
        await conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, page, section, content,
                                    content_hash, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                [
                    (
                        document_id,
                        c.index,
                        c.page,
                        c.section,
                        c.content,
                        c.content_hash,
                        c.token_count,
                        known[c.content_hash],
                    )
                    for c in chunks
                ],
            )

    return IngestResult(
        document_id=document_id,
        filename=filename,
        status="updated" if existing else "created",
        num_chunks=len(chunks),
        embedded_chunks=len(to_embed),
        reused_chunks=len(chunks) - len(to_embed),
        embedding_tokens=embedding_tokens,
    )
