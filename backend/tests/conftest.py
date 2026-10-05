import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.config import Settings
from app.models import RetrievedChunk
from app.observability import Trace
from app.providers.base import Completion, Embeddings, StreamChunk, Usage

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))  # so tests can import the `evals` package


class FakeProvider:
    """A scripted stand-in for the LLM: returns queued replies and records every call."""

    name = "fake"
    embedding_id = "fake:test:3"

    def __init__(self, replies: list[str] | None = None, stream_text: str = "") -> None:
        self.replies = list(replies or [])
        self.stream_text = stream_text
        self.calls: list[dict[str, object]] = []

    async def embed(self, texts: list[str], *, for_query: bool = False) -> Embeddings:
        self.calls.append({"kind": "embed", "texts": texts, "for_query": for_query})
        return Embeddings([[1.0, 0.0, 0.0] for _ in texts], Usage(input_tokens=len(texts)))

    async def generate(self, system: str, prompt: str, *, fast: bool = False) -> Completion:
        self.calls.append({"kind": "generate", "system": system, "prompt": prompt, "fast": fast})
        return Completion(self.replies.pop(0), Usage(input_tokens=10, output_tokens=5))

    async def stream(self, system: str, prompt: str) -> AsyncIterator[StreamChunk]:
        self.calls.append({"kind": "stream", "system": system, "prompt": prompt})
        for word in self.stream_text.split(" "):
            yield StreamChunk(text=word + " ")
        yield StreamChunk(usage=Usage(input_tokens=100, output_tokens=20))


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, provider="gemini", gemini_api_key="test")


@pytest.fixture
def trace(settings: Settings) -> Trace:
    return Trace(settings, trace_id="test-trace")


def make_chunk(chunk_id: int, content: str = "text", **overrides: object) -> RetrievedChunk:
    fields: dict[str, object] = {
        "id": chunk_id,
        "document": "manual.md",
        "section": "Battery",
        "page": None,
        "content": content,
    }
    return RetrievedChunk.model_validate({**fields, **overrides})
