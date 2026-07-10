"""Simple in-memory per-key rate limiting.

Guards the expensive cloud-API calls against a single user spamming (which
would run up cost and latency). In-memory is fine for the single-instance
free-tier deployment; a multi-instance setup would need a shared store.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_calls: int, per_seconds: float) -> None:
        self._max_calls = max_calls
        self._per_seconds = per_seconds
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        window_start = now - self._per_seconds
        hits = self._hits[key]

        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= self._max_calls:
            return False

        hits.append(now)
        return True


# Default: at most 8 AI requests per 30 seconds per chat.
message_limiter = RateLimiter(max_calls=8, per_seconds=30.0)
