"""The two retrievers. Each returns rows ordered best-first."""

from app.db import Pool, Row, fetch_all, to_pgvector

_COLUMNS = "c.id, d.filename AS document, c.section, c.page, c.content"


async def vector_search(pool: Pool, embedding: list[float], k: int) -> list[Row]:
    """Nearest neighbours by cosine distance (`<=>`), served by the HNSW index."""
    literal = to_pgvector(embedding)
    return await fetch_all(
        pool,
        f"""
        SELECT {_COLUMNS}, 1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
        """,
        (literal, literal, k),
    )


async def fulltext_search(pool: Pool, query: str, k: int) -> list[Row]:
    """Keyword search over the generated tsvector column, served by the GIN index.

    plainto_tsquery ANDs every term, which returns nothing for most natural
    language questions ("what is the max wind speed for takeoff" would need
    all of those words in one chunk). So the terms are OR-ed instead and
    ts_rank_cd puts the chunks matching the most terms first.
    """
    return await fetch_all(
        pool,
        f"""
        WITH q AS (
            SELECT to_tsquery(
                'english', replace(plainto_tsquery('english', %s)::text, ' & ', ' | ')
            ) AS query
        )
        SELECT {_COLUMNS}, ts_rank_cd(c.tsv, q.query) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id, q
        WHERE c.tsv @@ q.query
        ORDER BY score DESC, c.id
        LIMIT %s
        """,
        (query, k),
    )
