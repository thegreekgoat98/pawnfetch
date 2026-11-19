from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from pawnfetch.chesscom.client import ChessComClient, PlayerNotFoundError
from pawnfetch.chesscom.models import (
    Game,
    Leaderboards,
    PlayerProfile,
    PlayerStats,
    Streamer,
)
from web.app.cache import TTLCache
from web.app.openings import OpeningsSummary, summarize
from web.app.rivals import HeadToHead, Meeting, head_to_head, index_meetings
from web.app.roast import Roast, build_roast

PLAYER_TTL = 15 * 60
NOT_FOUND_TTL = 60
LEADERBOARDS_TTL = 30 * 60
STREAMERS_TTL = 5 * 60  # chess.com refreshes live status about every 5 minutes
GAMES_TTL = 30 * 60
# Openings, roasts and head-to-heads use the player's most recent games: newest months
# first, until this many games or this many months. A very active player can have 600+
# games (2-3 MB) in a month.
RECENT_GAMES = 300
RECENT_MONTHS = 3

T = TypeVar("T")

_NOT_FOUND = object()


class ServiceBusyError(Exception):
    """Another game download is running; the caller should try again in a few seconds."""


@dataclass
class PlayerData:
    profile: PlayerProfile
    stats: PlayerStats


@dataclass
class GameInsights:
    """Everything built from one download of a player's recent games. The games aren't kept."""

    openings: OpeningsSummary
    roast: Roast | None  # None: too few games
    meetings: dict[str, list[Meeting]]  # opponent -> games against them


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
        # Game downloads take seconds, so they get their own lock: they never hold up
        # profile lookups. At most two chess.com requests are therefore in flight at once.
        self._games = threading.Lock()

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

    def get_leaderboards(self) -> Leaderboards:
        return self._cached("leaderboards", LEADERBOARDS_TTL, self._client.get_leaderboards)

    def get_streamers(self) -> list[Streamer]:
        return self._cached("streamers", STREAMERS_TTL, self._client.get_streamers)

    def get_openings(self, username: str) -> OpeningsSummary:
        return self._insights(username).openings

    def get_roast(self, username: str) -> Roast | None:
        return self._insights(username).roast

    def get_head_to_head(self, username: str, opponent: str) -> HeadToHead:
        """`username`'s record against `opponent`, from `username`'s recent games."""
        meetings = self._insights(username).meetings.get(opponent.strip().lower(), [])
        return head_to_head(meetings)

    def _insights(self, username: str) -> GameInsights:
        name = username.strip().lower()
        key = f"games:{name}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        # Don't queue behind another download: waiting would tie up a server thread for
        # seconds. The page retries shortly instead (see the openings route).
        if not self._games.acquire(blocking=False):
            raise ServiceBusyError
        try:
            cached = self._cache.get(key)  # filled while we were checking?
            if cached is None:
                games = self._recent_games(name)
                cached = GameInsights(
                    openings=summarize(name, games),
                    roast=build_roast(name, games),
                    meetings=index_meetings(name, games),
                )
                self._cache.set(key, cached, GAMES_TTL)
        finally:
            self._games.release()
        return cached  # type: ignore[return-value]

    def _recent_games(self, username: str) -> list[Game]:
        games: list[Game] = []
        for year, month in reversed(self._client.get_game_months(username)[-RECENT_MONTHS:]):
            games = self._client.get_month_games(username, year, month) + games
            if len(games) >= RECENT_GAMES:
                break
        return games[-RECENT_GAMES:]

    def _cached(self, key: str, ttl: float, fetch: Callable[[], T]) -> T:
        cached = self._cache.get(key)
        if cached is None:
            with self._upstream:
                # Re-check: another request may have filled the cache while we waited.
                cached = self._cache.get(key)
                if cached is None:
                    cached = fetch()
                    self._cache.set(key, cached, ttl)
        return cached  # type: ignore[return-value]

    def close(self) -> None:
        self._client.close()
