"""Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, 2009)."""

from collections import defaultdict
from collections.abc import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]], k: int = 60
) -> list[tuple[int, float]]:
    """Merge ranked lists of ids into one list of (id, score), best first.

    score(id) = sum over lists of 1 / (k + rank), with rank starting at 1.

    RRF uses only ranks, never raw scores. That matters here because cosine
    similarity (0..1) and ts_rank (unbounded) are on different scales and
    cannot be added meaningfully. `k` damps the advantage of rank 1 over
    rank 2; 60 is the value from the paper and is rarely worth tuning.
    """
    scores: defaultdict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (k + rank)
    # Tie-break on id so the output is deterministic.
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
