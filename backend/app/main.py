import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import apply_schema, open_pool
from app.guardrails import RateLimiter
from app.observability import configure_logging, log_event
from app.providers import create_provider
from app.routes import chat, documents, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    app.state.pool = await open_pool(settings.database_url)
    await apply_schema(app.state.pool)
    app.state.provider = create_provider(settings)
    app.state.rate_limiter = RateLimiter(
        settings.rate_limit_requests, settings.rate_limit_window_seconds
    )
    log_event("app.started", provider=settings.provider)
    yield
    await app.state.pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Streaming RAG Chat", lifespan=lifespan)

    @app.middleware("http")
    async def trace_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Give every request a trace id, return it as a header, and log one line."""
        request.state.trace_id = uuid.uuid4().hex[:16]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        log_event(
            "http.request",
            trace_id=request.state.trace_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            # For streaming routes this is time to response headers, not to end of stream.
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response

    # Added last so it is the outermost layer: CORS headers are set even on error responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    return app


app = create_app()
