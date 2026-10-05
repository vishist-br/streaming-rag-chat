"""Structure-aware chunking with overlap. Pure functions, no I/O.

Rules, in order:
1. A chunk never crosses a section boundary (sections come from headings).
2. Inside a section, whole paragraphs are packed until `target_tokens`.
3. A paragraph larger than the target is split at sentence boundaries.
4. Consecutive chunks of one section share ~`overlap_tokens` of trailing text,
   so a fact that straddles a boundary is fully inside at least one chunk.
"""

import hashlib
import re
from dataclasses import dataclass
from itertools import groupby

from app.ingestion.parsers import Block
from app.providers.base import estimate_tokens

SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    section: str
    page: int | None
    token_count: int
    content_hash: str

    @property
    def embedding_text(self) -> str:
        """What gets embedded: the section title gives a short chunk its context."""
        return f"{self.section}\n\n{self.content}" if self.section else self.content


@dataclass(frozen=True)
class _Piece:
    """A paragraph, or one sentence of a paragraph that was too big to keep whole."""

    text: str
    page: int | None
    starts_paragraph: bool


def chunk_blocks(
    blocks: list[Block], target_tokens: int = 400, overlap_tokens: int = 60
) -> list[Chunk]:
    if overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be smaller than target_tokens")
    chunks: list[Chunk] = []
    for section, group in groupby(blocks, key=lambda b: b.section):
        pieces = [p for block in group for p in _to_pieces(block, target_tokens)]
        for text, page in _pack(pieces, target_tokens, overlap_tokens):
            digest = hashlib.sha256(f"{section}\n{text}".encode()).hexdigest()
            chunks.append(
                Chunk(
                    index=len(chunks),
                    content=text,
                    section=section,
                    page=page,
                    token_count=estimate_tokens(text),
                    content_hash=digest,
                )
            )
    return chunks


def _to_pieces(block: Block, target_tokens: int) -> list[_Piece]:
    if estimate_tokens(block.text) <= target_tokens:
        return [_Piece(block.text, block.page, starts_paragraph=True)]
    parts = [p for s in SENTENCE_END_RE.split(block.text) for p in _split_long(s, target_tokens)]
    return [_Piece(part, block.page, starts_paragraph=(i == 0)) for i, part in enumerate(parts)]


def _split_long(sentence: str, target_tokens: int) -> list[str]:
    """Last resort for a single sentence over the target (tables, minified text)."""
    if estimate_tokens(sentence) <= target_tokens:
        return [sentence]
    parts: list[str] = []
    current: list[str] = []
    for word in sentence.split():
        if current and estimate_tokens(" ".join([*current, word])) > target_tokens:
            parts.append(" ".join(current))
            current = []
        current.append(word)
    parts.append(" ".join(current))
    return parts


def _pack(
    pieces: list[_Piece], target_tokens: int, overlap_tokens: int
) -> list[tuple[str, int | None]]:
    """Greedily fill chunks, carrying a tail of the previous chunk forward as overlap."""
    out: list[tuple[str, int | None]] = []
    current: list[_Piece] = []
    carried = 0  # how many pieces at the start of `current` are overlap from the last chunk

    def emit() -> None:
        page = current[carried].page  # page of the first new piece, not of the overlap
        out.append((_render(current), page))

    for piece in pieces:
        size = sum(estimate_tokens(p.text) for p in current) + estimate_tokens(piece.text)
        if len(current) > carried and size > target_tokens:
            emit()
            current = _tail(current, overlap_tokens)
            carried = len(current)
        current.append(piece)
    if len(current) > carried:
        emit()
    return out


def _tail(pieces: list[_Piece], overlap_tokens: int) -> list[_Piece]:
    """The trailing pieces that fit in the overlap budget (sentences of the last one if none)."""
    tail: list[_Piece] = []
    budget = overlap_tokens
    for piece in reversed(pieces):
        cost = estimate_tokens(piece.text)
        if cost > budget:
            break
        tail.insert(0, piece)
        budget -= cost
    if tail or not pieces:
        return tail
    last = pieces[-1]
    for sentence in reversed(SENTENCE_END_RE.split(last.text)):
        cost = estimate_tokens(sentence)
        if cost > budget:
            break
        tail.insert(0, _Piece(sentence, last.page, starts_paragraph=False))
        budget -= cost
    return tail


def _render(pieces: list[_Piece]) -> str:
    text = ""
    for piece in pieces:
        separator = "" if not text else ("\n\n" if piece.starts_paragraph else " ")
        text += separator + piece.text
    return text
