"""Offline demo provider: runs the whole app without an API key.

It is NOT a language model. Embeddings are hashed bag-of-words vectors and
"answers" are sentences copied from the retrieved sources. It exists so the
pipeline can be demoed and integration-tested end to end; quality numbers
must come from a real provider.
"""

import asyncio
import hashlib
import math
import re
from collections.abc import AsyncIterator

from app.generation.prompt import DONT_KNOW
from app.providers.base import Completion, Embeddings, StreamChunk, Usage, estimate_tokens

WORD_RE = re.compile(r"[a-z0-9]+")
SOURCE_RE = re.compile(r'<source id="(\d+)"[^>]*>\n(.*?)\n</source>', re.DOTALL)
QUESTION_RE = re.compile(r"<question>\n(.*?)\n</question>", re.DOTALL)
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i in is it of on or that the this to "  # noqa: SIM905
    "was what when where which who why will with".split()
)


def _stem(word: str) -> str:
    """Crude suffix stripping so "lasts" matches "last". Good enough for a demo."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _terms(text: str) -> list[str]:
    return [_stem(w) for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS]


class LocalProvider:
    name = "local"

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim
        self.embedding_id = f"local:hashed-bow:{dim}"

    async def embed(self, texts: list[str], *, for_query: bool = False) -> Embeddings:
        vectors = [self._hash_embed(t) for t in texts]
        return Embeddings(vectors, Usage(input_tokens=sum(estimate_tokens(t) for t in texts)))

    def _hash_embed(self, text: str) -> list[float]:
        """Feature hashing: each word adds +1 or -1 to one bucket, then L2-normalise."""
        vector = [0.0] * self._dim
        for term in _terms(text):
            digest = hashlib.md5(term.encode()).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dim
            vector[bucket] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    async def generate(self, system: str, prompt: str, *, fast: bool = False) -> Completion:
        # No model to ask. Callers (rewrite, rerank) fall back when the reply is empty.
        return Completion(text="", usage=Usage(input_tokens=estimate_tokens(system + prompt)))

    async def stream(self, system: str, prompt: str) -> AsyncIterator[StreamChunk]:
        answer = self._extractive_answer(prompt)
        for word in answer.split(" "):
            await asyncio.sleep(0.015)  # so the UI visibly streams
            yield StreamChunk(text=word + " ")
        yield StreamChunk(
            usage=Usage(
                input_tokens=estimate_tokens(system + prompt),
                output_tokens=estimate_tokens(answer),
            )
        )

    def _extractive_answer(self, prompt: str) -> str:
        """Pick the sentence from each top source that shares most words with the question."""
        question = QUESTION_RE.search(prompt)
        query_terms = set(_terms(question.group(1) if question else ""))
        picked: list[str] = []
        for source_id, body in SOURCE_RE.findall(prompt)[:3]:
            sentences = re.split(r"(?<=[.!?])\s+|\n+", body)
            best = max(sentences, key=lambda s: len(query_terms & set(_terms(s))), default="")
            if len(query_terms & set(_terms(best))) >= 2:
                picked.append(f"{best.strip().rstrip('.')} [{source_id}].")
        return " ".join(picked) if picked else DONT_KNOW
