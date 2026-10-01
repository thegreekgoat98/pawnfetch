import json
from pathlib import Path

import httpx
import pytest
import respx

from pawnfetch.client import (
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
    return json.loads((FIXTURES / name).read_text())


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