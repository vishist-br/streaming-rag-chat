"""Evaluate retrieval and answer quality over the golden dataset.

Usage (from the repo root, with Postgres running and GEMINI_API_KEY set):

    python evals/run_evals.py                  # all three configurations
    python evals/run_evals.py --retrieval-only # skip generation and the LLM judge
    python evals/run_evals.py --limit 5        # quick smoke run

Writes evals/RESULTS.md and evals/results.json. With PROVIDER=local the
numbers are printed but NOT written: the offline provider is not a real
model, so its scores must never be presented as results.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, get_args

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `evals.metrics` imports when run as a script

from app.config import Settings, get_settings  # noqa: E402
from app.db import Pool, apply_schema, fetch_all, open_pool  # noqa: E402
from app.generation.prompt import DONT_KNOW, SYSTEM_PROMPT, build_answer_prompt  # noqa: E402
from app.ingestion.pipeline import ingest_document  # noqa: E402
from app.models import RetrievalMode, RetrievedChunk  # noqa: E402
from app.observability import Trace  # noqa: E402
from app.providers import create_provider  # noqa: E402
from app.providers.base import Provider  # noqa: E402
from app.retrieval.pipeline import retrieve  # noqa: E402

from evals.metrics import (  # noqa: E402
    first_relevant_rank,
    hit_rate,
    mean,
    mean_reciprocal_rank,
    parse_judge_reply,
)

EVALS_DIR = ROOT / "evals"
SAMPLE_DOCS_DIR = ROOT / "sample_docs"
SAMPLE_DOC_SUFFIXES = {".md", ".txt", ".pdf"}
NOT_A_SAMPLE = {"LICENSE.md"}
ALL_MODES: tuple[RetrievalMode, ...] = get_args(RetrievalMode.__value__)

JUDGE_SYSTEM = """You grade answers produced by a question-answering system.

Score two things from 1 (worst) to 5 (best):
- faithfulness: is every factual claim in the answer supported by the sources? \
5 = fully supported, 1 = mostly unsupported or contradicted. Ignore whether the answer is complete.
- relevance: does the answer address the question and agree with the reference answer? \
5 = answers it correctly, 1 = does not answer it or is wrong.

Reply with only JSON: {"faithfulness": <1-5>, "relevance": <1-5>}"""


@dataclass
class QuestionResult:
    id: str
    question: str
    rank: int | None  # rank of the evidence chunk; None for a miss or an unanswerable question
    answer: str | None = None
    faithfulness: int | None = None
    relevance: int | None = None
    abstained: bool | None = None  # unanswerable questions only
    latency_ms: float = 0.0
    cost_usd: float = 0.0


def load_golden(limit: int | None) -> list[dict[str, Any]]:
    lines = (EVALS_DIR / "golden.jsonl").read_text().splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    return items[:limit] if limit else items


async def ingest_sample_docs(pool: Pool, provider: Provider, settings: Settings) -> None:
    paths = sorted(
        p
        for p in SAMPLE_DOCS_DIR.iterdir()
        if p.suffix in SAMPLE_DOC_SUFFIXES and p.name not in NOT_A_SAMPLE
    )
    for path in paths:
        result = await ingest_document(pool, provider, settings, path.name, path.read_bytes())
        print(f"  ingest {path.name}: {result.status}, {result.num_chunks} chunks")
    # Other documents in the database would compete with the sample docs and skew the scores.
    sample_names = {p.name for p in paths}
    rows = await fetch_all(pool, "SELECT filename FROM documents")
    extra = sorted(row["filename"] for row in rows if row["filename"] not in sample_names)
    if extra:
        sys.exit(f"The database also contains {extra}. Remove them and run the evals again.")


async def with_retry[T](call: Callable[[], Awaitable[T]], attempts: int = 4) -> T:
    """Retry with backoff: free-tier API keys hit rate limits quickly."""
    for attempt in range(attempts):
        try:
            return await call()
        except Exception as error:
            if attempt == attempts - 1:
                raise
            delay = 5 * 2**attempt
            print(f"    retrying in {delay}s after: {error!s:.120}")
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def judge(
    provider: Provider, item: dict[str, Any], chunks: list[RetrievedChunk], answer: str
) -> tuple[int | None, int | None]:
    sources = "\n\n".join(f"[{n}] {c.content}" for n, c in enumerate(chunks, start=1))
    prompt = (
        f"Question: {item['question']}\n\nReference answer: {item['expected_answer']}\n\n"
        f"Sources:\n{sources}\n\nAnswer to grade:\n{answer}"
    )
    reply = await with_retry(partial(provider.generate, JUDGE_SYSTEM, prompt))
    scores = parse_judge_reply(reply.text)
    return (scores.faithfulness, scores.relevance) if scores else (None, None)


async def evaluate_mode(
    pool: Pool,
    provider: Provider,
    settings: Settings,
    mode: RetrievalMode,
    golden: list[dict[str, Any]],
    retrieval_only: bool,
) -> list[QuestionResult]:
    results: list[QuestionResult] = []
    for item in golden:
        trace = Trace(settings)
        chunks = await with_retry(
            partial(retrieve, pool, provider, settings, item["question"], mode, trace)
        )
        answerable = item["document"] is not None
        rank = (
            first_relevant_rank(
                [(c.document, c.content) for c in chunks], item["document"], item["evidence"]
            )
            if answerable
            else None
        )
        result = QuestionResult(id=item["id"], question=item["question"], rank=rank)

        if not retrieval_only:
            prompt = build_answer_prompt(item["question"], chunks)
            with trace.stage("generation"):
                completion = await with_retry(partial(provider.generate, SYSTEM_PROMPT, prompt))
            trace.add_usage("generation", completion.usage, "generation")
            result.answer = completion.text.strip()
            if answerable:
                result.faithfulness, result.relevance = await judge(
                    provider, item, chunks, result.answer
                )
            else:
                result.abstained = DONT_KNOW.lower() in result.answer.lower()

        # Judge calls are not part of serving a request, so they are left out of latency/cost.
        summary = trace.summary()
        result.latency_ms = sum(stage["ms"] for stage in summary["stages"].values())
        result.cost_usd = summary["cost_usd"]
        results.append(result)
        status = "n/a" if not answerable else (f"rank {rank}" if rank else "MISS")
        print(f"  [{mode}] {item['id']}: {status}")
    return results


def summarize(
    mode: str, results: list[QuestionResult], golden: list[dict[str, Any]]
) -> dict[str, Any]:
    answerable_ids = {item["id"] for item in golden if item["document"] is not None}
    answerable = [r for r in results if r.id in answerable_ids]
    unanswerable = [r for r in results if r.id not in answerable_ids]
    abstentions = [float(r.abstained) for r in unanswerable if r.abstained is not None]
    return {
        "mode": mode,
        "questions": len(results),
        "hit_rate": hit_rate([r.rank for r in answerable]),
        "mrr": mean_reciprocal_rank([r.rank for r in answerable]),
        "faithfulness": mean([float(r.faithfulness) for r in answerable if r.faithfulness]),
        "relevance": mean([float(r.relevance) for r in answerable if r.relevance]),
        "judged": sum(r.faithfulness is not None for r in answerable),
        "abstention_rate": mean(abstentions),
        "mean_latency_ms": mean([r.latency_ms for r in results]),
        "mean_cost_usd": mean([r.cost_usd for r in results]),
        "misses": [r.id for r in answerable if r.rank is None],
    }


def fmt(value: float | None, pattern: str = "{:.2f}") -> str:
    return "n/a" if value is None else pattern.format(value)


def render_markdown(
    summaries: list[dict[str, Any]], settings: Settings, provider: Provider, retrieval_only: bool
) -> str:
    labels = {"vector": "Vector only", "hybrid": "Hybrid (RRF)", "hybrid_rerank": "Hybrid + rerank"}
    k = settings.final_k
    rows = "\n".join(
        f"| {labels[s['mode']]} | {s['hit_rate']:.2f} | {s['mrr']:.2f} | {fmt(s['faithfulness'])} "
        f"| {fmt(s['relevance'])} | {fmt(s['abstention_rate'])} "
        f"| {fmt(s['mean_latency_ms'], '{:.0f}')} | {fmt(s['mean_cost_usd'], '{:.5f}')} |"
        for s in summaries
    )
    misses = "\n".join(
        f"- **{labels[s['mode']]}**: {', '.join(s['misses']) or 'none'}" for s in summaries
    )
    note = (
        "\nRun with `--retrieval-only`: answers were not generated or judged.\n"
        if retrieval_only
        else ""
    )
    return f"""# Evaluation results

Generated by `evals/run_evals.py` on {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Do not edit by hand.

- Provider: `{provider.name}`; generation and judge model `{settings.generation_model}`; \
rerank model `{settings.fast_model}`; embeddings `{provider.embedding_id}`
- Chunking: {settings.chunk_target_tokens} target tokens, {settings.chunk_overlap_tokens} overlap
- Candidates: {settings.vector_k} vector + {settings.fulltext_k} keyword, \
{settings.rerank_candidates} reranked, top {k} kept
- Questions: {summaries[0]["questions"]} from `evals/golden.jsonl`
{note}
| Configuration | Hit rate@{k} | MRR@{k} | Faithfulness (1-5) | Relevance (1-5) \
| Abstention rate | Mean latency (ms) | Mean cost (USD) |
|---|---|---|---|---|---|---|---|
{rows}

## How to read this

- **Hit rate@{k}**: share of answerable questions whose evidence passage is in the top {k} chunks.
- **MRR@{k}**: mean of 1/rank of that passage; higher means it is nearer the top.
- **Faithfulness / Relevance**: mean LLM-judge scores over answerable questions.
- **Abstention rate**: share of unanswerable questions where the system replied "{DONT_KNOW}"
- **Latency and cost** are per question, for retrieval plus generation, without judge calls.

## Retrieval misses

{misses}
"""


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--configs", nargs="+", choices=ALL_MODES, default=list(ALL_MODES))
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--retrieval-only", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    provider = create_provider(settings)
    golden = load_golden(args.limit)
    pool = await open_pool(settings.database_url)
    try:
        await apply_schema(pool)
        print("Ingesting sample documents")
        await ingest_sample_docs(pool, provider, settings)
        all_results: dict[str, list[QuestionResult]] = {}
        for mode in args.configs:
            print(f"Evaluating {mode}")
            all_results[mode] = await evaluate_mode(
                pool, provider, settings, mode, golden, args.retrieval_only
            )
    finally:
        await pool.close()

    summaries = [summarize(mode, results, golden) for mode, results in all_results.items()]
    markdown = render_markdown(summaries, settings, provider, args.retrieval_only)
    table = markdown.split("\n## How to read this")[0]
    if provider.name == "local":
        print("\n" + table)
        print("PROVIDER=local is a smoke test only: nothing was written to RESULTS.md.")
        return
    (EVALS_DIR / "RESULTS.md").write_text(markdown)
    raw = {
        "summaries": summaries,
        "results": {mode: [asdict(r) for r in results] for mode, results in all_results.items()},
    }
    (EVALS_DIR / "results.json").write_text(json.dumps(raw, indent=2) + "\n")
    print("\n" + table)
    print("Wrote evals/RESULTS.md and evals/results.json")


if __name__ == "__main__":
    asyncio.run(main())
