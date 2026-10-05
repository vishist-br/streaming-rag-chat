"""The chat pipeline as an async generator of Server-Sent Events.

Event order: [rewrite] -> sources -> token* -> metrics -> done   (or: error)
Sources are sent before the first token so the UI can render citations
as soon as they appear in the text.
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from app.config import Settings
from app.db import Pool
from app.generation.prompt import DONT_KNOW, SYSTEM_PROMPT, build_answer_prompt, extract_citations
from app.generation.rewrite import rewrite_question
from app.guardrails import looks_like_injection
from app.models import ChatRequest
from app.observability import Trace, log_event
from app.providers.base import Provider
from app.retrieval.pipeline import retrieve


def sse(event: str, data: dict[str, Any]) -> str:
    """Format one Server-Sent Event. json.dumps escapes newlines, so data is one line."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def chat_events(
    pool: Pool, provider: Provider, settings: Settings, request: ChatRequest, trace: Trace
) -> AsyncIterator[str]:
    answer = ""
    outcome = "ok"
    try:
        history = request.history[-settings.max_history_messages :]
        query = await rewrite_question(
            provider, history, request.question, trace, settings.max_question_chars
        )
        if query != request.question:
            yield sse("rewrite", {"query": query})

        chunks = await retrieve(pool, provider, settings, query, request.mode, trace)
        for chunk in chunks:
            chunk.flagged = looks_like_injection(chunk.content)
            if chunk.flagged:
                log_event("guardrail.injection_suspected", trace_id=trace.trace_id, chunk=chunk.id)
        yield sse("sources", {"sources": [chunk.model_dump() for chunk in chunks]})

        first_token_ms: float | None = None
        if not chunks:
            # Nothing retrieved (e.g. no documents yet): answer without paying for an LLM call.
            answer = DONT_KNOW
            yield sse("token", {"text": answer})
        else:
            started = time.perf_counter()
            with trace.stage("generation"):
                async for piece in provider.stream(
                    SYSTEM_PROMPT, build_answer_prompt(query, chunks)
                ):
                    if piece.usage:
                        trace.add_usage("generation", piece.usage, "generation")
                    if piece.text:
                        if first_token_ms is None:
                            first_token_ms = (time.perf_counter() - started) * 1000
                        answer += piece.text
                        yield sse("token", {"text": piece.text})

        yield sse(
            "metrics",
            {
                **trace.summary(),
                "mode": request.mode,
                "first_token_ms": None if first_token_ms is None else round(first_token_ms, 1),
                "cited": extract_citations(answer, len(chunks)),
            },
        )
        yield sse("done", {})
    except Exception:
        outcome = "error"
        log_event("chat.failed", level=logging.ERROR, trace_id=trace.trace_id, exc_info=True)
        # Never leak internals to the client; the trace id links to the full log line.
        message = f"Something went wrong (trace {trace.trace_id})."
        yield sse("error", {"message": message})
    finally:
        # Runs on success, on error, and when the client disconnects mid-stream.
        log_event(
            "chat.completed",
            outcome=outcome,
            mode=request.mode,
            question_chars=len(request.question),
            answer_chars=len(answer),
            **trace.summary(),
        )
