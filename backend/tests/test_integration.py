"""Full pipeline against a real Postgres + pgvector, using the offline provider.

Skipped unless RUN_INTEGRATION=1 (CI sets it and provides the database).
"""

import os
from collections.abc import AsyncIterator

import pytest

from app.config import Settings
from app.db import Pool, apply_schema, fetch_all, open_pool
from app.ingestion.pipeline import ingest_document
from app.observability import Trace
from app.providers.local import LocalProvider
from app.retrieval.pipeline import retrieve

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="RUN_INTEGRATION != 1"),
]

DOC_V1 = (
    b"# Drone\n\n## Battery\nThe battery lasts 42 minutes.\n\n"
    b"## Errors\nE-417 means the geofence database is out of date.\n"
)
DOC_V2 = DOC_V1 + b"\n## Motors\nThere are four brushless motors.\n"
NAME = "integration_test_doc.md"


@pytest.fixture
async def pool() -> AsyncIterator[Pool]:
    settings = Settings(provider="local")
    pool = await open_pool(settings.database_url)
    await apply_schema(pool)
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM documents WHERE filename = %s", (NAME,))
    yield pool
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM documents WHERE filename = %s", (NAME,))
    await pool.close()


async def test_ingestion_is_idempotent_and_reuses_embeddings(pool: Pool) -> None:
    settings, provider = Settings(provider="local"), LocalProvider()

    created = await ingest_document(pool, provider, settings, NAME, DOC_V1)
    assert (created.status, created.num_chunks, created.embedded_chunks) == ("created", 2, 2)

    again = await ingest_document(pool, provider, settings, NAME, DOC_V1)
    assert (again.status, again.embedded_chunks) == ("unchanged", 0)

    updated = await ingest_document(pool, provider, settings, NAME, DOC_V2)
    assert (updated.status, updated.num_chunks) == ("updated", 3)
    assert (updated.embedded_chunks, updated.reused_chunks) == (1, 2)

    rows = await fetch_all(
        pool,
        "SELECT section FROM chunks c JOIN documents d ON d.id = c.document_id "
        "WHERE d.filename = %s ORDER BY chunk_index",
        (NAME,),
    )
    assert [r["section"] for r in rows] == ["Drone > Battery", "Drone > Errors", "Drone > Motors"]


async def test_hybrid_retrieval_finds_an_exact_code_by_keyword(pool: Pool) -> None:
    settings, provider = Settings(provider="local"), LocalProvider()
    await ingest_document(pool, provider, settings, NAME, DOC_V1)

    chunks = await retrieve(pool, provider, settings, "E-417", "hybrid", Trace(settings))
    ours = [c for c in chunks if c.document == NAME]
    assert ours[0].section == "Drone > Errors"
    assert ours[0].fulltext_rank is not None

    vector_only = await retrieve(pool, provider, settings, "E-417", "vector", Trace(settings))
    assert all(c.fulltext_rank is None for c in vector_only)
