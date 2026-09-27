import json
from pathlib import Path

import httpx
import respx

from pawnfetch.client import ChessComClient, PlayerNotFoundError

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

    with ChessComClient() as client:
        try:
            client.get_profile("no-such-user-xyz")
            assert False, "expected PlayerNotFoundError"
        except PlayerNotFoundError as exc:
            assert exc.username == "no-such-user-xyz"