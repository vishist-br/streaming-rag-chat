"""Input limits, prompt-injection handling for retrieved text, and per-IP rate limiting."""

import re
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request

# Phrases that address the model rather than inform the reader. This is a
# tripwire for logging and for flagging the chunk in the UI, not a defence
# on its own: the real defence is that sources are delimited and the system
# prompt says to treat them as data.
INJECTION_RE = re.compile(
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)"
    r"|disregard (all |any |the )?(previous|prior|above|earlier)"
    r"|you are now\b"
    r"|new instructions?:"
    r"|(reveal|print|repeat) (your |the )?(system )?prompt"
    r"|do not (tell|inform) the user",
    re.IGNORECASE,
)
# Tags our prompt uses as delimiters. Document text must not be able to close them.
DELIMITER_RE = re.compile(r"<(/?)(source|sources|question)\b", re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return INJECTION_RE.search(text) is not None


def neutralize_delimiters(text: str) -> str:
    """Escape our own delimiter tags so a document cannot break out of its <source> block."""
    return DELIMITER_RE.sub(r"&lt;\1\2", text)


class RateLimiter:
    """Sliding-window limiter kept in memory.

    Correct for a single process. With several replicas each one would count
    separately, so a shared store (Redis) would be needed; see docs/DECISIONS.md.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> float:
        """Record a request. Returns 0 if allowed, else the seconds until a slot frees up."""
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._max:
            return self._window - (now - hits[0])
        hits.append(now)
        return 0.0


def rate_limit(request: Request) -> None:
    """FastAPI dependency. Keyed on the socket peer address.

    Behind a reverse proxy this is the proxy's IP; use the proxy's
    X-Forwarded-For handling (uvicorn --proxy-headers) in that setup.
    """
    limiter: RateLimiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    retry_after = limiter.check(client_ip)
    if retry_after > 0:
        raise HTTPException(
            429,
            "Too many requests. Please slow down.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
