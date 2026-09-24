"""Per-claim tool/AI call limiter. Demo-grade, in-process."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

from app.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def hit(self, claim_id: str) -> bool:
        """Record a call. Return True if allowed."""
        limit = get_settings().rate_limit_per_claim
        with self._lock:
            self._counts[claim_id] += 1
            return self._counts[claim_id] <= limit

    def remaining(self, claim_id: str) -> int:
        limit = get_settings().rate_limit_per_claim
        with self._lock:
            return max(0, limit - self._counts[claim_id])

    def reset(self, claim_id: str) -> None:
        with self._lock:
            self._counts[claim_id] = 0


rate_limiter = RateLimiter()
