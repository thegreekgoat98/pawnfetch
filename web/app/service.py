from __future__ import annotations

import threading
from dataclasses import dataclass

from pawnfetch.chesscom.client import ChessComClient, PlayerNotFoundError
from pawnfetch.chesscom.models import PlayerProfile, PlayerStats
from web.app.cache import TTLCache

PLAYER_TTL = 15 * 60
NOT_FOUND_TTL = 60

_NOT_FOUND = object()


@dataclass
class PlayerData:
    profile: PlayerProfile
    stats: PlayerStats


class PlayerService:
    """Cached chess.com lookups. Upstream calls are serialized: chess.com 429s parallel requests."""

    def __init__(
        self,
        client: ChessComClient | None = None,
        cache: TTLCache | None = None,
        ttl: float = PLAYER_TTL,
        not_found_ttl: float = NOT_FOUND_TTL,
    ):
        self._client = client or ChessComClient()
        self._cache = cache or TTLCache()
        self._ttl = ttl
        self._not_found_ttl = not_found_ttl
        self._upstream = threading.Lock()

    def get_player(self, username: str) -> PlayerData:
        key = f"player:{username.strip().lower()}"
        cached = self._cache.get(key)
        if cached is None:
            with self._upstream:
                # Re-check: another request may have filled the cache while we waited.
                cached = self._cache.get(key)
                if cached is None:
                    cached = self._fetch(key, username)
        if cached is _NOT_FOUND:
            raise PlayerNotFoundError(username.strip())
        return cached  # type: ignore[return-value]

    def _fetch(self, key: str, username: str) -> object:
        try:
            data = PlayerData(
                profile=self._client.get_profile(username),
                stats=self._client.get_stats(username),
            )
        except PlayerNotFoundError:
            self._cache.set(key, _NOT_FOUND, self._not_found_ttl)
            raise
        self._cache.set(key, data, self._ttl)
        return data

    def close(self) -> None:
        self._client.close()
