from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TTLCache:
    """Small in-process cache; values expire after a per-entry TTL. `None` means a miss."""

    def __init__(self, max_entries: int = 1000, clock: Callable[[], float] = time.monotonic):
        self._max_entries = max_entries
        self._clock = clock
        self._items: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> object | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= self._clock():
                del self._items[key]
                return None
            return value

    def set(self, key: str, value: object, ttl: float) -> None:
        with self._lock:
            if key not in self._items and len(self._items) >= self._max_entries:
                self._evict()
            self._items[key] = (self._clock() + ttl, value)

    def _evict(self) -> None:
        now = self._clock()
        for key in [k for k, (expires_at, _) in self._items.items() if expires_at <= now]:
            del self._items[key]
        if len(self._items) >= self._max_entries:
            del self._items[next(iter(self._items))]
