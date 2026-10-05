import pytest

from app.ingestion.parsers import (
    Block,
    UnsupportedFileTypeError,
    parse_document,
    parse_markdown,
    parse_text,
)


def test_markdown_sections_are_heading_paths() -> None:
    blocks = parse_markdown("# Guide\nIntro.\n\n## Battery\nLasts long.\n\n### Storage\nKeep cool.")
    assert blocks == [
        Block("Intro.", "Guide"),
        Block("Lasts long.", "Guide > Battery"),
        Block("Keep cool.", "Guide > Battery > Storage"),
    ]


def test_sibling_heading_replaces_the_previous_one() -> None:
    blocks = parse_markdown("# Guide\n## A\n### Deep\ntext a\n## B\ntext b")
    assert [b.section for b in blocks] == ["Guide > A > Deep", "Guide > B"]


def test_hash_inside_a_code_fence_is_not_a_heading() -> None:
    blocks = parse_markdown("# Title\n```\n# just a comment\n\nx = 1\n```\nAfter.")
    assert len(blocks) == 1
    assert blocks[0].section == "Title"
    assert "# just a comment" in blocks[0].text


def test_text_is_split_on_blank_lines() -> None:
    assert [b.text for b in parse_text("One.\n\n\nTwo.\n  \nThree.")] == ["One.", "Two.", "Three."]


def test_parse_document_dispatches_on_extension() -> None:
    assert parse_document("NOTES.MD", b"# H\nbody")[0].section == "H"
    assert parse_document("notes.txt", b"# H\nbody")[0].section == ""


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        parse_document("malware.exe", b"")
