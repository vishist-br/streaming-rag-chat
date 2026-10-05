"""The small interface the pipeline depends on.

Everything outside this package talks to `Provider`, never to an SDK, so
swapping Gemini for another model means writing one new class.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Embeddings:
    vectors: list[list[float]]
    usage: Usage


@dataclass(frozen=True)
class Completion:
    text: str
    usage: Usage


@dataclass(frozen=True)
class StreamChunk:
    """A piece of streamed text. The final chunk carries the usage totals."""

    text: str = ""
    usage: Usage | None = None


class Provider(Protocol):
    name: str
    # Identifies the vector space. Stored per document so that switching
    # embedding models triggers a re-embed instead of mixing spaces.
    embedding_id: str

    async def embed(self, texts: list[str], *, for_query: bool = False) -> Embeddings: ...

    async def generate(self, system: str, prompt: str, *, fast: bool = False) -> Completion:
        """One-shot completion. `fast=True` selects the cheaper model."""
        ...

    def stream(self, system: str, prompt: str) -> AsyncIterator[StreamChunk]: ...


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 characters per token for English)."""
    return max(1, len(text) // 4)
