"""Tiny in-process cache for policy lookups."""

from __future__ import annotations

from threading import Lock
from typing import Any


class SimpleCache:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._hits = 0
        self._misses = 0
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._data:
                self._hits += 1
                return self._data[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "size": len(self._data)}


policy_cache = SimpleCache()
