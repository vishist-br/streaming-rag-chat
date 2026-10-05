"""Retrieval orchestration. The three modes are exactly what the evals compare."""

from app.config import Settings
from app.db import Pool, Row
from app.models import RetrievalMode, RetrievedChunk
from app.observability import Trace
from app.providers.base import Provider
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.rerank import rerank
from app.retrieval.search import fulltext_search, vector_search


async def retrieve(
    pool: Pool,
    provider: Provider,
    settings: Settings,
    question: str,
    mode: RetrievalMode,
    trace: Trace,
) -> list[RetrievedChunk]:
    with trace.stage("embed_query"):
        embedded = await provider.embed([question], for_query=True)
    trace.add_usage("embed_query", embedded.usage, "embedding")

    with trace.stage("vector_search"):
        vector_rows = await vector_search(pool, embedded.vectors[0], settings.vector_k)

    fulltext_rows: list[Row] = []
    if mode != "vector":
        with trace.stage("fulltext_search"):
            fulltext_rows = await fulltext_search(pool, question, settings.fulltext_k)

    vector_ids = [row["id"] for row in vector_rows]
    fulltext_ids = [row["id"] for row in fulltext_rows]
    rows_by_id = {row["id"]: row for row in [*vector_rows, *fulltext_rows]}
    # With a single list RRF keeps its order, so "vector" mode needs no special case.
    fused = reciprocal_rank_fusion([vector_ids, fulltext_ids], k=settings.rrf_k)

    candidates = [
        RetrievedChunk(
            **{key: rows_by_id[chunk_id][key] for key in ("id", "document", "section", "page")},
            content=rows_by_id[chunk_id]["content"],
            vector_rank=vector_ids.index(chunk_id) + 1 if chunk_id in vector_ids else None,
            fulltext_rank=fulltext_ids.index(chunk_id) + 1 if chunk_id in fulltext_ids else None,
        )
        for chunk_id, _score in fused
    ]

    if mode == "hybrid_rerank":
        return await rerank(
            provider, question, candidates[: settings.rerank_candidates], settings.final_k, trace
        )
    return candidates[: settings.final_k]
