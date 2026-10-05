from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.deps import PoolDep, ProviderDep, SettingsDep
from app.generation.stream import chat_events
from app.guardrails import rate_limit
from app.models import ChatRequest
from app.observability import Trace

router = APIRouter()


@router.post("/api/chat", dependencies=[Depends(rate_limit)])
async def chat(
    body: ChatRequest, request: Request, pool: PoolDep, provider: ProviderDep, settings: SettingsDep
) -> StreamingResponse:
    if len(body.question) > settings.max_question_chars:
        raise HTTPException(
            422, f"question is longer than {settings.max_question_chars} characters"
        )
    trace = Trace(settings, trace_id=request.state.trace_id)
    return StreamingResponse(
        chat_events(pool, provider, settings, body, trace),
        media_type="text/event-stream",
        # no-cache + X-Accel-Buffering stop proxies (nginx) from buffering the stream.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
