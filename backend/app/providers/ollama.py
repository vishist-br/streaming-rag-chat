"""Ollama implementation of Provider: real open models running locally over HTTP.

Proves the provider interface is swappable, and lets the whole pipeline
(including the evals) run with real models and no API key.
"""

import json
import math
from collections.abc import AsyncIterator

import httpx

from app.config import Settings
from app.providers.base import Completion, Embeddings, StreamChunk, Usage


class OllamaProvider:
    name = "ollama"

    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._model = settings.ollama_generation_model
        self._embedding_model = settings.ollama_embedding_model
        self._dim = settings.embedding_dim
        # Local models can take a while on the first call while they load into memory.
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url, timeout=300, transport=transport
        )
        self.embedding_id = f"ollama:{self._embedding_model}:{self._dim}"

    async def embed(self, texts: list[str], *, for_query: bool = False) -> Embeddings:
        # nomic-embed-text is trained with task prefixes for the two sides of retrieval.
        prefix = "search_query: " if for_query else "search_document: "
        response = await self._client.post(
            "/api/embed",
            json={"model": self._embedding_model, "input": [prefix + t for t in texts]},
        )
        response.raise_for_status()
        data = response.json()
        vectors = [_normalize(v) for v in data["embeddings"]]
        if vectors and len(vectors[0]) != self._dim:
            raise RuntimeError(
                f"{self._embedding_model} returns {len(vectors[0])} dimensions, "
                f"but the schema expects {self._dim}"
            )
        return Embeddings(vectors, Usage(input_tokens=data.get("prompt_eval_count", 0)))

    def _chat_body(self, system: str, prompt: str, temperature: float, stream: bool) -> dict:  # type: ignore[type-arg]
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": stream,
            # The default context window (2048-4096 tokens) would silently cut off the sources.
            "options": {"temperature": temperature, "num_ctx": 8192},
        }

    async def generate(self, system: str, prompt: str, *, fast: bool = False) -> Completion:
        # One local model serves both roles, so `fast` changes nothing here.
        response = await self._client.post(
            "/api/chat", json=self._chat_body(system, prompt, 0.0, stream=False)
        )
        response.raise_for_status()
        data = response.json()
        return Completion(text=data["message"]["content"], usage=_usage(data))

    async def stream(self, system: str, prompt: str) -> AsyncIterator[StreamChunk]:
        body = self._chat_body(system, prompt, 0.2, stream=True)
        async with self._client.stream("POST", "/api/chat", json=body) as response:
            response.raise_for_status()
            # Ollama streams newline-delimited JSON; the last object has done=true and usage.
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                text = data.get("message", {}).get("content", "")
                if text:
                    yield StreamChunk(text=text)
                if data.get("done"):
                    yield StreamChunk(usage=_usage(data))


def _usage(data: dict) -> Usage:  # type: ignore[type-arg]
    return Usage(
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
    )


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]
