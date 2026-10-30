import json
from pathlib import Path

import httpx
import pytest
import respx

from pawnfetch.chesscom.client import (
    ChessComClient,
    ChessComConnectionError,
    ChessComHTTPError,
    ChessComRateLimitError,
    ChessComResponseError,
    ChessComServerError,
    ChessComUnavailableError,
    PlayerNotFoundError,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@respx.mock
def test_get_profile_returns_parsed_profile():
    data = load_fixture("profile_hikaru.json")
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        return_value=httpx.Response(200, json=data)
    )

    with ChessComClient() as client:
        profile = client.get_profile("hikaru")

    assert profile.username == data["username"]
    assert profile.player_id == data["player_id"]


@respx.mock
def test_get_stats_returns_parsed_stats():
    data = load_fixture("stats_hikaru.json")
    respx.get("https://api.chess.com/pub/player/hikaru/stats").mock(
        return_value=httpx.Response(200, json=data)
    )

    with ChessComClient() as client:
        stats = client.get_stats("hikaru")

    assert stats.username == "hikaru"
    if "chess_blitz" in data:
        assert stats.blitz is not None
        assert stats.blitz.rating == data["chess_blitz"]["last"]["rating"]


@respx.mock
def test_get_profile_raises_on_404():
    respx.get("https://api.chess.com/pub/player/no-such-user-xyz").mock(
        return_value=httpx.Response(404, json={"code": 0, "message": "not found"})
    )

    with ChessComClient() as client, pytest.raises(PlayerNotFoundError) as error:
        client.get_profile("no-such-user-xyz")
    assert error.value.username == "no-such-user-xyz"


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, ChessComHTTPError),
        (410, ChessComUnavailableError),
        (429, ChessComRateLimitError),
        (500, ChessComServerError),
    ],
)
@respx.mock
def test_get_profile_maps_http_errors(status_code, error_type):
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        return_value=httpx.Response(status_code, json={})
    )

    with ChessComClient() as client, pytest.raises(error_type):
        client.get_profile("hikaru")


@respx.mock
def test_get_profile_rejects_invalid_json():
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        return_value=httpx.Response(200, content=b"not json")
    )

    with ChessComClient() as client, pytest.raises(
        ChessComResponseError, match="not valid JSON"
    ):
        client.get_profile("hikaru")


@respx.mock
def test_get_profile_rejects_unexpected_schema():
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        return_value=httpx.Response(200, json={})
    )

    with ChessComClient() as client, pytest.raises(
        ChessComResponseError, match="unexpected player profile"
    ):
        client.get_profile("hikaru")


@respx.mock
def test_get_profile_rejects_non_object_json():
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        return_value=httpx.Response(200, json=[])
    )

    with ChessComClient() as client, pytest.raises(
        ChessComResponseError, match="unexpected format"
    ):
        client.get_profile("hikaru")


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (httpx.ConnectError("connection refused"), "reach chess.com"),
        (httpx.TimeoutException("timed out"), "timed out"),
    ],
)
@respx.mock
def test_get_profile_maps_network_errors(exception, message):
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        side_effect=exception
    )

    with ChessComClient() as client, pytest.raises(
        ChessComConnectionError, match=message
    ):
        client.get_profile("hikaru")


@pytest.mark.parametrize(
    ("username", "raw_path"),
    [
        ("a/b", b"/pub/player/a%2Fb"),
        ("a?x", b"/pub/player/a%3Fx"),
        (" HiKaru ", b"/pub/player/hikaru"),
    ],
)
@respx.mock
def test_username_is_quoted_as_one_path_segment(username, raw_path):
    route = respx.route(host="api.chess.com").mock(
        return_value=httpx.Response(200, json={"username": "x", "player_id": 1})
    )

    with ChessComClient() as client:
        client.get_profile(username)

    assert route.calls.last.request.url.raw_path == raw_path


@respx.mock
def test_not_found_reports_the_full_original_username():
    respx.route(host="api.chess.com").mock(return_value=httpx.Response(404, json={}))

    with ChessComClient() as client, pytest.raises(PlayerNotFoundError) as error:
        client.get_profile(" a/b ")

    assert error.value.username == "a/b"


@respx.mock
def test_get_stats_normalizes_the_username():
    respx.route(host="api.chess.com").mock(return_value=httpx.Response(200, json={}))

    with ChessComClient() as client:
        stats = client.get_stats(" HiKaru ")

    assert stats.username == "hikaru"


LEADERBOARDS_URL = "https://api.chess.com/pub/leaderboards"


@respx.mock
def test_get_leaderboards_parses_every_board():
    respx.get(LEADERBOARDS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("leaderboards.json"))
    )

    with ChessComClient() as client:
        boards = client.get_leaderboards()

    blitz = boards.get("live_blitz")
    assert [e.rank for e in blitz] == [1, 2, 3, 4, 10]
    leader = blitz[0]
    assert (leader.username, leader.score, leader.title) == ("Hikaru", 3450, "GM")
    assert leader.country_code == "US"
    assert leader.wins == 37650 and leader.total == 37650 + 5664 + 4432
    assert blitz[3].name == "Ediz Gürel"
    assert boards.get("rush")[0].score == 93
    assert boards.get("not_a_board") == []


@respx.mock
def test_leaderboard_trends_are_signed():
    respx.get(LEADERBOARDS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("leaderboards.json"))
    )

    with ChessComClient() as client:
        boards = client.get_leaderboards()

    assert boards.get("live_blitz")[0].rank_change == 0
    assert boards.get("live_blitz")[4].rank_change == 1


def test_leaderboard_entry_tolerates_missing_optional_fields():
    from pawnfetch.chesscom.models import LeaderboardEntry

    entry = LeaderboardEntry.from_api(
        {
            "rank": 7,
            "username": "anon",
            "score": 1500,
            "trend_rank": {"direction": -1, "delta": 3},
        }
    )

    assert entry.name is None and entry.title is None and entry.country_code is None
    assert entry.rank_change == -3
    assert entry.score_change == 0
    assert entry.win_pct == 0.0


@respx.mock
def test_leaderboards_404_is_not_reported_as_a_missing_player():
    respx.get(LEADERBOARDS_URL).mock(return_value=httpx.Response(404, json={}))

    with ChessComClient() as client, pytest.raises(ChessComHTTPError):
        client.get_leaderboards()


@respx.mock
def test_malformed_leaderboards_raise_response_error():
    respx.get(LEADERBOARDS_URL).mock(
        return_value=httpx.Response(200, json={"live_blitz": [{"username": "x"}]})
    )

    with ChessComClient() as client, pytest.raises(ChessComResponseError):
        client.get_leaderboards()