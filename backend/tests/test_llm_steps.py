"""Rewrite and rerank, with the LLM replaced by FakeProvider."""

from app.generation.rewrite import rewrite_question
from app.models import ChatMessage
from app.observability import Trace
from app.retrieval.rerank import build_rerank_prompt, parse_ranking, rerank
from tests.conftest import FakeProvider, make_chunk

HISTORY = [
    ChatMessage(role="user", content="How long does the battery last?"),
    ChatMessage(role="assistant", content="About 42 minutes [1]."),
]


async def test_first_turn_is_not_rewritten_and_costs_no_llm_call(trace: Trace) -> None:
    provider = FakeProvider()
    assert await rewrite_question(provider, [], "What is E-417?", trace, 2000) == "What is E-417?"
    assert provider.calls == []


async def test_follow_up_is_rewritten_with_the_fast_model(trace: Trace) -> None:
    provider = FakeProvider(replies=['"How long does the battery take to charge?"\n'])
    result = await rewrite_question(provider, HISTORY, "and to charge?", trace, 2000)
    assert result == "How long does the battery take to charge?"
    (call,) = provider.calls
    assert call["fast"] is True
    assert "user: How long does the battery last?" in str(call["prompt"])
    assert "Latest question: and to charge?" in str(call["prompt"])
    assert trace.stages["rewrite"].input_tokens == 10


async def test_rewrite_falls_back_to_the_original_on_a_bad_reply(trace: Trace) -> None:
    for bad_reply in ["", "   ", "x" * 5000]:
        provider = FakeProvider(replies=[bad_reply])
        assert await rewrite_question(provider, HISTORY, "and to charge?", trace, 2000) == (
            "and to charge?"
        )


def test_parse_ranking_handles_noise_duplicates_and_bad_numbers() -> None:
    assert parse_ranking("[3, 1, 2]", 3) == [2, 0, 1]
    assert parse_ranking("Sure! Here you go: [2,2,9,0,1] hope it helps", 3) == [1, 0]
    assert parse_ranking("no array here", 3) is None
    assert parse_ranking("[]", 3) is None
    assert parse_ranking("[99]", 3) is None


def test_rerank_prompt_numbers_passages_and_truncates_them() -> None:
    prompt = build_rerank_prompt("q?", [make_chunk(1, "a" * 5000), make_chunk(2, "short")])
    assert "[1] (manual.md | Battery)" in prompt
    assert "[2] (manual.md | Battery)\nshort" in prompt
    assert len(prompt) < 2000


async def test_rerank_reorders_and_keeps_top_k(trace: Trace) -> None:
    chunks = [make_chunk(i) for i in (10, 20, 30, 40)]
    provider = FakeProvider(replies=["[3, 1]"])
    result = await rerank(provider, "q", chunks, top_k=3, trace=trace)
    # Ranked ones first, then the rest in their original (fused) order.
    assert [c.id for c in result] == [30, 10, 20]
    assert provider.calls[0]["fast"] is True


async def test_rerank_keeps_fused_order_when_reply_is_unusable(trace: Trace) -> None:
    chunks = [make_chunk(i) for i in (10, 20, 30)]
    result = await rerank(FakeProvider(replies=["I cannot do that"]), "q", chunks, 2, trace)
    assert [c.id for c in result] == [10, 20]


async def test_rerank_skips_the_llm_for_zero_or_one_candidate(trace: Trace) -> None:
    provider = FakeProvider()
    assert await rerank(provider, "q", [], 5, trace) == []
    assert len(await rerank(provider, "q", [make_chunk(1)], 5, trace)) == 1
    assert provider.calls == []
