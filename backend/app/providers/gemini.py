"""Gemini implementation of Provider, using the official google-genai SDK."""

import math
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.config import Settings
from app.providers.base import Completion, Embeddings, StreamChunk, Usage, estimate_tokens


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (or use PROVIDER=local for the demo)")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._settings = settings
        self.embedding_id = f"gemini:{settings.embedding_model}:{settings.embedding_dim}"

    async def embed(self, texts: list[str], *, for_query: bool = False) -> Embeddings:
        # gemini-embedding-2 has no task_type parameter; the task goes in the text.
        # Each text is its own Content, otherwise the API returns one aggregated vector.
        if for_query:
            prompts = [f"task: search result | query: {t}" for t in texts]
        else:
            prompts = [f"title: none | text: {t}" for t in texts]
        response = await self._client.aio.models.embed_content(
            model=self._settings.embedding_model,
            contents=[types.Content(parts=[types.Part(text=p)]) for p in prompts],
            config=types.EmbedContentConfig(output_dimensionality=self._settings.embedding_dim),
        )
        vectors = [_normalize(list(e.values or [])) for e in response.embeddings or []]
        if len(vectors) != len(texts):
            raise RuntimeError(f"expected {len(texts)} embeddings, got {len(vectors)}")
        # The embedding response carries no token counts, so this is an estimate.
        tokens = sum(estimate_tokens(p) for p in prompts)
        return Embeddings(vectors=vectors, usage=Usage(input_tokens=tokens))

    async def generate(self, system: str, prompt: str, *, fast: bool = False) -> Completion:
        model = self._settings.fast_model if fast else self._settings.generation_model
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.0),
        )
        return Completion(text=response.text or "", usage=_usage(response.usage_metadata))

    async def stream(self, system: str, prompt: str) -> AsyncIterator[StreamChunk]:
        stream = await self._client.aio.models.generate_content_stream(
            model=self._settings.generation_model,
            contents=prompt,
            # Low temperature: we want the answer to follow the sources, not be creative.
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.2),
        )
        usage = Usage()
        async for chunk in stream:
            if chunk.usage_metadata:
                usage = _usage(chunk.usage_metadata)
            if chunk.text:
                yield StreamChunk(text=chunk.text)
        yield StreamChunk(usage=usage)


def _usage(meta: types.GenerateContentResponseUsageMetadata | None) -> Usage:
    if meta is None:
        return Usage()
    return Usage(
        input_tokens=meta.prompt_token_count or 0,
        # Thinking tokens are billed as output.
        output_tokens=(meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0),
    )
