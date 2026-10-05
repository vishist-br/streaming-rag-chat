"""Pure metric helpers for the eval script. Unit tested in backend/tests/test_eval_metrics.py."""

import json
import re
from dataclasses import dataclass

JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def normalize(text: str) -> str:
    """Lower-case and collapse whitespace so line wrapping does not break matching."""
    return " ".join(text.lower().split())


def first_relevant_rank(
    retrieved: list[tuple[str, str]], document: str, evidence: str
) -> int | None:
    """1-based rank of the first chunk that is from `document` and contains `evidence`.

    `retrieved` is a list of (document, content), best first. Matching on an
    evidence phrase instead of a chunk id keeps the golden set valid when the
    chunking parameters change.
    """
    needle = normalize(evidence)
    for rank, (chunk_document, content) in enumerate(retrieved, start=1):
        if chunk_document == document and needle in normalize(content):
            return rank
    return None


def hit_rate(ranks: list[int | None]) -> float:
    """Share of questions whose evidence chunk was retrieved at all."""
    return sum(rank is not None for rank in ranks) / len(ranks) if ranks else 0.0


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    """Mean of 1/rank (0 for a miss). Rewards putting the right chunk first."""
    return sum(1.0 / rank for rank in ranks if rank) / len(ranks) if ranks else 0.0


@dataclass(frozen=True)
class JudgeScores:
    faithfulness: int  # 1-5: is every claim supported by the retrieved sources?
    relevance: int  # 1-5: does the answer address the question and match the reference?


def parse_judge_reply(text: str) -> JudgeScores | None:
    """Parse {"faithfulness": n, "relevance": n}. None if the reply is unusable."""
    match = JSON_OBJECT_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        scores = JudgeScores(int(data["faithfulness"]), int(data["relevance"]))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if not (1 <= scores.faithfulness <= 5 and 1 <= scores.relevance <= 5):
        return None
    return scores


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
