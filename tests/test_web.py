import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from pawnfetch.chesscom.client import (
    ChessComConnectionError,
    ChessComRateLimitError,
    PlayerNotFoundError,
)
from pawnfetch.chesscom.models import PlayerProfile, PlayerStats
from web.app.main import create_app
from web.app.service import PlayerData

FIXTURES = Path(__file__).parent / "fixtures"


class FakeService:
    def __init__(self):
        self.error: Exception | None = None

    def get_player(self, username: str) -> PlayerData:
        if self.error:
            raise self.error
        profile = json.loads((FIXTURES / "profile_hikaru.json").read_text())
        stats = json.loads((FIXTURES / "stats_hikaru.json").read_text())
        return PlayerData(
            PlayerProfile.from_api(profile), PlayerStats.from_api("hikaru", stats)
        )

    def close(self) -> None:
        pass


service = FakeService()
client = TestClient(create_app(service))


@pytest.fixture(autouse=True)
def _reset_service():
    service.error = None


def test_home_renders_search_form():
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="search-form"' in response.text
    assert 'data-theme="dark"' in response.text


def test_home_shows_real_ratings_in_featured_card():
    response = client.get("/")
    assert "featured player" in response.text
    assert "3443" in response.text  # blitz rating from the fixture


def test_home_hides_featured_card_when_chess_com_fails():
    service.error = ChessComConnectionError("offline")
    response = client.get("/")
    assert response.status_code == 200
    assert "featured player" not in response.text


def test_home_tries_another_player_when_featured_one_is_missing():
    calls = []

    class FirstMissing(FakeService):
        def get_player(self, username):
            calls.append(username)
            if len(calls) == 1:
                raise PlayerNotFoundError(username)
            return super().get_player(username)

    response = TestClient(create_app(FirstMissing())).get("/")
    assert len(calls) == 2
    assert calls[0] != calls[1]
    assert "featured player" in response.text


def test_search_redirects_to_lowercase_player():
    response = client.get("/search", params={"u": " Hikaru "}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/player/hikaru"


@pytest.mark.parametrize("bad", ["", "ab", "has space", "a" * 26, "<script>"])
def test_search_rejects_invalid_usernames(bad):
    response = client.get("/search", params={"u": bad}, follow_redirects=False)
    assert response.status_code == 422
    assert "3-25 characters" in response.text


def test_search_does_not_reflect_markup():
    response = client.get("/search", params={"u": "<script>x</script>"})
    assert "<script>x" not in response.text


def test_player_page_shows_profile_and_stats():
    response = client.get("/player/hikaru")
    assert response.status_code == 200
    text = response.text
    assert "Hikaru Nakamura" in text
    assert "GM" in text
    assert "3400" in text and "3443" in text and "2838" in text
    assert "2814" in text  # FIDE
    assert "https://www.chess.com/member/Hikaru" in text


def test_player_page_canonicalizes_username_case():
    response = client.get("/player/HIKARU", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == "/player/hikaru"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (PlayerNotFoundError("ghost"), 404),
        (ChessComRateLimitError("slow down"), 429),
        (ChessComConnectionError("offline"), 502),
    ],
)
def test_player_errors_render_error_page(error, status):
    service.error = error
    response = client.get("/player/ghost")
    assert response.status_code == status
    assert "Back to search" in response.text


def test_unknown_page_uses_error_template():
    response = client.get("/nope")
    assert response.status_code == 404
    assert "That square" in response.text


def test_invalid_player_username_is_404():
    assert client.get("/player/a%20b").status_code == 404


def test_static_assets_served():
    assert client.get("/static/favicon.svg").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200
