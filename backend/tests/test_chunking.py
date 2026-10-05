import pytest

from app.ingestion.chunking import chunk_blocks
from app.ingestion.parsers import Block
from app.providers.base import estimate_tokens


def sentences(count: int, prefix: str = "Sentence") -> str:
    return " ".join(f"{prefix} number {i} has some words in it." for i in range(count))


def test_small_blocks_in_one_section_are_packed_into_one_chunk() -> None:
    blocks = [Block("First paragraph.", "Intro"), Block("Second paragraph.", "Intro")]
    chunks = chunk_blocks(blocks, target_tokens=100, overlap_tokens=10)
    assert len(chunks) == 1
    assert chunks[0].content == "First paragraph.\n\nSecond paragraph."
    assert chunks[0].section == "Intro"


def test_chunks_never_cross_a_section_boundary() -> None:
    blocks = [Block("About batteries.", "Battery"), Block("About motors.", "Motors")]
    chunks = chunk_blocks(blocks, target_tokens=100, overlap_tokens=10)
    assert [(c.section, c.content) for c in chunks] == [
        ("Battery", "About batteries."),
        ("Motors", "About motors."),
    ]


def test_oversized_paragraph_is_split_at_sentence_boundaries_within_the_budget() -> None:
    target, overlap = 50, 10
    chunks = chunk_blocks([Block(sentences(40), "Long")], target, overlap)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= target + overlap
        assert chunk.content.endswith(".")  # no sentence was cut in half


def test_consecutive_chunks_of_a_section_overlap() -> None:
    chunks = chunk_blocks([Block(sentences(40), "Long")], target_tokens=50, overlap_tokens=15)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        first_sentence = current.content.split(". ")[0]
        assert first_sentence in previous.content


def test_no_overlap_is_carried_across_sections() -> None:
    blocks = [Block(sentences(40, "Alpha"), "A"), Block(sentences(3, "Beta"), "B")]
    chunks = chunk_blocks(blocks, target_tokens=50, overlap_tokens=15)
    section_b = [c for c in chunks if c.section == "B"]
    assert len(section_b) == 1
    assert "Alpha" not in section_b[0].content


def test_no_text_is_lost() -> None:
    text = sentences(60)
    chunks = chunk_blocks([Block(text, "S")], target_tokens=40, overlap_tokens=8)
    joined = " ".join(c.content for c in chunks)
    for i in range(60):
        assert f"number {i} has" in joined


def test_single_sentence_longer_than_target_is_hard_split() -> None:
    giant = "word " * 400  # one "sentence" of ~500 tokens
    chunks = chunk_blocks([Block(giant.strip(), "S")], target_tokens=50, overlap_tokens=5)
    assert len(chunks) > 5
    assert all(estimate_tokens(c.content) <= 55 for c in chunks)


def test_indexes_are_sequential_and_hashes_are_stable() -> None:
    blocks = [Block(sentences(30), "A"), Block("Short.", "B")]
    first = chunk_blocks(blocks, 50, 10)
    second = chunk_blocks(blocks, 50, 10)
    assert [c.index for c in first] == list(range(len(first)))
    assert [c.content_hash for c in first] == [c.content_hash for c in second]


def test_same_text_in_different_sections_hashes_differently() -> None:
    a, b = chunk_blocks([Block("Same text.", "A"), Block("Same text.", "B")], 50, 10)
    assert a.content_hash != b.content_hash


def test_page_comes_from_the_first_new_piece_not_the_overlap() -> None:
    blocks = [Block(sentences(12), page=1), Block(sentences(12, "Other"), page=2)]
    chunks = chunk_blocks(blocks, target_tokens=110, overlap_tokens=20)
    assert chunks[0].page == 1
    assert chunks[-1].page == 2


def test_embedding_text_includes_the_section_title() -> None:
    (chunk,) = chunk_blocks([Block("Lasts 42 minutes.", "Battery > Flight Time")], 50, 10)
    assert chunk.embedding_text == "Battery > Flight Time\n\nLasts 42 minutes."


def test_empty_input_and_invalid_overlap() -> None:
    assert chunk_blocks([], 50, 10) == []
    with pytest.raises(ValueError):
        chunk_blocks([Block("x")], target_tokens=10, overlap_tokens=10)
