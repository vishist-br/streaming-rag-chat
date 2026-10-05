"""Turn a follow-up ("and how long does it take?") into a standalone search query.

Retrieval only sees one string. Without this step a follow-up would be
embedded without its subject and retrieve unrelated chunks.
"""

from app.models import ChatMessage
from app.observability import Trace
from app.providers.base import Provider

REWRITE_SYSTEM = (
    "Rewrite the user's latest question so it can be understood without the conversation. "
    "Resolve pronouns and references using the conversation. Keep it one short question. "
    "Do not answer it. If it is already standalone, return it unchanged. "
    "Reply with only the rewritten question."
)
HISTORY_MESSAGE_CHARS = 500  # an old answer only needs to contribute its topic


def build_rewrite_prompt(history: list[ChatMessage], question: str) -> str:
    turns = "\n".join(f"{m.role}: {m.content[:HISTORY_MESSAGE_CHARS]}" for m in history)
    return f"Conversation:\n{turns}\n\nLatest question: {question}"


async def rewrite_question(
    provider: Provider, history: list[ChatMessage], question: str, trace: Trace, max_chars: int
) -> str:
    if not history:
        return question  # first turn: nothing to resolve, skip the LLM call
    with trace.stage("rewrite"):
        completion = await provider.generate(
            REWRITE_SYSTEM, build_rewrite_prompt(history, question), fast=True
        )
    trace.add_usage("rewrite", completion.usage, "fast")
    rewritten = completion.text.strip().strip('"')
    # An empty or runaway reply must not break retrieval: fall back to the original.
    if not rewritten or len(rewritten) > max_chars:
        return question
    return rewritten
