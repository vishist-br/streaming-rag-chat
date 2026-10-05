"""Structured JSON logs and a per-request Trace that records latency, tokens and cost."""

import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.config import Settings
from app.providers.base import Usage

logger = logging.getLogger("rag")

type ModelKind = Literal["generation", "fast", "embedding"]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """One JSON line per event, e.g. log_event("chat.completed", trace_id=..., total_ms=...)."""
    logger.log(level, event, extra={"fields": fields})


@dataclass
class StageMetrics:
    ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class Trace:
    """Collects metrics for one request. Passed down the pipeline explicitly."""

    def __init__(self, settings: Settings, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.stages: dict[str, StageMetrics] = {}
        self._started = time.perf_counter()
        # The offline demo provider calls no paid API, so its cost is zero.
        self._scale = 0.0 if settings.provider == "local" else 1.0
        self._prices: dict[ModelKind, tuple[float, float]] = {
            "generation": (settings.price_generation_input, settings.price_generation_output),
            "fast": (settings.price_fast_input, settings.price_fast_output),
            "embedding": (settings.price_embedding_input, 0.0),
        }

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            metrics = self.stages.setdefault(name, StageMetrics())
            metrics.ms += (time.perf_counter() - started) * 1000

    def add_usage(self, stage: str, usage: Usage, kind: ModelKind) -> None:
        input_price, output_price = self._prices[kind]
        metrics = self.stages.setdefault(stage, StageMetrics())
        metrics.input_tokens += usage.input_tokens
        metrics.output_tokens += usage.output_tokens
        tokens_cost = usage.input_tokens * input_price + usage.output_tokens * output_price
        metrics.cost_usd += self._scale * tokens_cost / 1_000_000

    def summary(self) -> dict[str, Any]:
        stages = self.stages.values()
        return {
            "trace_id": self.trace_id,
            "total_ms": round((time.perf_counter() - self._started) * 1000, 1),
            "input_tokens": sum(s.input_tokens for s in stages),
            "output_tokens": sum(s.output_tokens for s in stages),
            "cost_usd": round(sum(s.cost_usd for s in stages), 6),
            "stages": {
                name: {**asdict(s), "ms": round(s.ms, 1), "cost_usd": round(s.cost_usd, 6)}
                for name, s in self.stages.items()
            },
        }
