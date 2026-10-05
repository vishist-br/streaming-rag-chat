import json

import pytest

from evals.metrics import (
    JudgeScores,
    first_relevant_rank,
    hit_rate,
    mean_reciprocal_rank,
    normalize,
    parse_judge_reply,
)
from tests.conftest import REPO_ROOT


def test_first_relevant_rank_needs_the_right_document_and_the_evidence() -> None:
    retrieved = [
        ("other.md", "lasts 42 minutes"),
        ("manual.md", "unrelated"),
        ("manual.md", "The battery\n  lasts 42   Minutes in calm air."),
    ]
    assert first_relevant_rank(retrieved, "manual.md", "lasts 42 minutes") == 3
    assert first_relevant_rank(retrieved, "manual.md", "not there") is None


def test_hit_rate_and_mrr() -> None:
    ranks = [1, 2, None, 4]
    assert hit_rate(ranks) == 0.75
    assert mean_reciprocal_rank(ranks) == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)
    assert hit_rate([]) == 0.0
    assert mean_reciprocal_rank([]) == 0.0


def test_parse_judge_reply() -> None:
    assert parse_judge_reply('{"faithfulness": 5, "relevance": 4}') == JudgeScores(5, 4)
    assert parse_judge_reply('```json\n{"faithfulness": 3, "relevance": 3}\n```') == JudgeScores(
        3, 3
    )
    assert parse_judge_reply('{"faithfulness": 9, "relevance": 4}') is None
    assert parse_judge_reply('{"faithfulness": 5}') is None
    assert parse_judge_reply("looks good to me") is None


def test_golden_dataset_is_consistent_with_the_sample_documents() -> None:
    """Every evidence phrase must really exist in its document, or hit rate is meaningless."""
    lines = (REPO_ROOT / "evals" / "golden.jsonl").read_text().splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    assert 20 <= len(items) <= 40
    assert len({item["id"] for item in items}) == len(items)
    for item in items:
        if item["type"] == "unanswerable":
            assert item["document"] is None and item["evidence"] is None
            continue
        document = (REPO_ROOT / "sample_docs" / item["document"]).read_text()
        assert normalize(item["evidence"]) in normalize(document), item["id"]
        assert item["expected_answer"]
