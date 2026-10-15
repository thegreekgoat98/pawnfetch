import json
from pathlib import Path

import httpx
import pytest
import respx

pytest.importorskip("fastapi")

from pawnfetch.chesscom.client import ChessComClient, PlayerNotFoundError
from web.app.cache import TTLCache
from web.app.filters import ago, duration
from web.app.service import PlayerService

FIXTURES = Path(__file__).parent / "fixtures"
API = "https://api.chess.com/pub/player"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_cache_entries_expire():
    clock = Clock()
    cache = TTLCache(clock=clock)
    cache.set("a", "value", ttl=10)
    assert cache.get("a") == "value"
    clock.now = 10
    assert cache.get("a") is None


def test_cache_evicts_oldest_when_full():
    cache = TTLCache(max_entries=2, clock=Clock())
    cache.set("a", 1, ttl=100)
    cache.set("b", 2, ttl=100)
    cache.set("c", 3, ttl=100)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


@respx.mock
def test_service_fetches_once_then_serves_from_cache():
    profile = respx.get(f"{API}/hikaru").mock(
        return_value=httpx.Response(200, json=load("profile_hikaru.json"))
    )
    stats = respx.get(f"{API}/hikaru/stats").mock(
        return_value=httpx.Response(200, json=load("stats_hikaru.json"))
    )
    service = PlayerService(ChessComClient())

    first = service.get_player("hikaru")
    second = service.get_player(" HIKARU ")

    assert first is second
    assert profile.call_count == 1
    assert stats.call_count == 1
    assert first.stats.fide == 2814
    assert first.stats.bullet.best_rating == 3570
    assert first.stats.puzzle_rush.score == 123
    assert first.profile.country_code == "US"


@respx.mock
def test_service_caches_not_found_briefly():
    clock = Clock()
    route = respx.get(f"{API}/ghost").mock(return_value=httpx.Response(404, json={}))
    service = PlayerService(ChessComClient(), cache=TTLCache(clock=clock), not_found_ttl=60)

    for _ in range(2):
        with pytest.raises(PlayerNotFoundError):
            service.get_player("ghost")
    assert route.call_count == 1

    clock.now = 61
    with pytest.raises(PlayerNotFoundError):
        service.get_player("ghost")
    assert route.call_count == 2


@respx.mock
def test_service_does_not_cache_upstream_errors():
    route = respx.get(f"{API}/hikaru").mock(return_value=httpx.Response(500))
    service = PlayerService(ChessComClient())

    for _ in range(2):
        with pytest.raises(Exception, match="server error"):
            service.get_player("hikaru")
    assert route.call_count == 2


def test_duration_formats():
    assert duration(45) == "45s"
    assert duration(600) == "10m"
    assert duration(32755) == "9h 5m"
    assert duration(200_000) == "2d 7h"
    assert duration(None) == "—"


def test_ago_formats():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert ago(now - timedelta(seconds=5), now) == "just now"
    assert ago(now - timedelta(hours=1), now) == "1 hour ago"
    assert ago(now - timedelta(days=3), now) == "3 days ago"
    assert ago(None) == "unknown"
