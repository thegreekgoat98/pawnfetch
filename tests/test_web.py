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
from pawnfetch.chesscom.models import (
    DailyPuzzle,
    Leaderboards,
    PlayerProfile,
    PlayerStats,
    Streamer,
)
from web.app.main import create_app
from web.app.service import PlayerData

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeService:
    def __init__(self):
        self.error: Exception | None = None
        self.puzzle_override: dict | None = None

    def get_player(self, username: str) -> PlayerData:
        if self.error:
            raise self.error
        profile = json.loads((FIXTURES / "profile_hikaru.json").read_text())
        stats = json.loads((FIXTURES / "stats_hikaru.json").read_text())
        return PlayerData(
            PlayerProfile.from_api(profile), PlayerStats.from_api("hikaru", stats)
        )

    def get_leaderboards(self) -> Leaderboards:
        if self.error:
            raise self.error
        return Leaderboards.from_api(fixture("leaderboards.json"))

    def get_streamers(self) -> list[Streamer]:
        if self.error:
            raise self.error
        return [Streamer.from_api(s) for s in fixture("streamers.json")["streamers"]]

    def get_daily_puzzle(self) -> DailyPuzzle:
        if self.error:
            raise self.error
        return DailyPuzzle.from_api(self.puzzle_override or fixture("puzzle.json"))

    def close(self) -> None:
        pass


service = FakeService()
client = TestClient(create_app(service))


@pytest.fixture(autouse=True)
def _reset_service():
    service.error = None
    service.puzzle_override = None


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


def test_home_links_to_leaderboards():
    assert 'href="/leaderboards"' in client.get("/").text


def test_leaderboards_redirects_to_default_board():
    response = client.get("/leaderboards", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/leaderboards/blitz"


def test_leaderboard_page_shows_podium_and_table():
    response = client.get("/leaderboards/blitz")
    assert response.status_code == 200
    text = response.text
    assert "Hikaru Nakamura" in text and "Magnus Carlsen" in text
    assert "Ediz Gürel" in text
    assert "3,450" in text
    assert 'href="/player/hikaru"' in text  # links use our lowercase player URLs
    assert 'href="/player/chesswarrior7197"' in text
    assert "1<span class=\"sr-only\"> places up</span>" in text  # ChessWarrior7197 moved up one place
    assert "W / D / L" in text
    assert 'aria-current="page"' in text


def test_leaderboard_marks_only_the_current_tab():
    text = client.get("/leaderboards/bughouse").text
    assert 'href="/leaderboards/bughouse" aria-current="page"' in text
    assert 'href="/leaderboards/blitz" aria-current' not in text


def test_player_without_name_shows_username():
    text = client.get("/leaderboards/bughouse").text
    assert "ShadowThinker1" in text


def test_puzzle_rush_board_has_no_win_loss_columns():
    text = client.get("/leaderboards/puzzle-rush").text
    assert "Best score" in text
    assert "W / D / L" not in text
    assert "Matthias Bluebaum" in text


def test_empty_board_shows_message():
    text = client.get("/leaderboards/daily").text  # not in the fixture
    assert "didn't send any players" in text


def test_hidden_boards_are_not_routes():
    assert client.get("/leaderboards/tactics").status_code == 404
    assert client.get("/leaderboards/nope").status_code == 404


@pytest.mark.parametrize(
    ("path", "active"),
    [
        ("/", "/"),
        ("/player/hikaru", "/"),
        ("/compare", "/compare"),
        ("/compare/hikaru/magnuscarlsen", "/compare"),
        ("/leaderboards/blitz", "/leaderboards"),
        ("/puzzle", "/puzzle"),
        ("/streamers", "/streamers"),
    ],
)
def test_header_nav_on_every_page_marks_current_section(path, active):
    text = client.get(path).text
    for href in ("/", "/compare", "/leaderboards", "/puzzle", "/streamers"):
        marked = f'href="{href}" aria-current="page"' in text
        assert marked == (href == active), href
    assert 'aria-label="Main"' in text


def test_header_nav_is_on_error_pages():
    text = client.get("/nope").text
    assert 'href="/leaderboards"' in text
    assert 'aria-current="page"' not in text


def test_home_links_to_every_live_feature():
    text = client.get("/").text
    for href in ("/compare", "/leaderboards", "/puzzle", "/streamers"):
        assert f'href="{href}" class="after:absolute' in text, href


def test_streamers_page_lists_live_streamers_first():
    text = client.get("/streamers").text
    live_section, _, offline_section = text.partition("All other chess.com streamers")
    assert "Live now" in live_section
    # official streamers before community ones
    assert live_section.index("annacramling") < live_section.index("kingnb") < live_section.index("Msb2")
    assert "Watch on YouTube" in live_section and "Watch on Twitch" in live_section
    assert "Community" in live_section
    assert 'href="https://twitch.tv/annacramling"' in live_section
    assert 'href="/player/msb2"' in live_section
    assert "RoadtoGMNEPAL" in offline_section and "liveflagonly" in offline_section


def test_streamers_page_drops_unsafe_stream_links():
    text = client.get("/streamers").text
    assert "javascript:" not in text
    assert "sneakylink" in text  # still listed, just without a Watch link


def test_streamers_page_when_nobody_is_live(monkeypatch):
    monkeypatch.setattr(service, "get_streamers", list)
    assert "Nobody is live" in client.get("/streamers").text


def test_puzzle_page_renders_a_playable_board():
    response = client.get("/puzzle")
    assert response.status_code == 200
    text = response.text
    assert "Royally Distracted" in text
    assert "White to move" in text
    assert text.count("data-sq=") == 64
    assert text.split('data-sq="')[1].startswith('a8"')  # White at the bottom: a8 is top-left
    assert 'aria-label="f4, white knight"' in text
    assert 'id="puzzle-data"' in text and "/static/js/puzzle.js" in text
    assert '"from": "f4"' in text and '"to": "g6"' in text
    assert "1. Nxg6+" in text and "2. Qh4#" in text
    assert 'href="https://www.chess.com/daily/2026-10-30"' in text


def test_puzzle_page_flips_the_board_for_black():
    service.puzzle_override = dict(
        fixture("puzzle.json"), fen="4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1", pgn="1... d5 2. exd6"
    )
    text = client.get("/puzzle").text
    assert "Black to move" in text
    assert text.index('data-sq="h1"') < text.index('data-sq="a8"')
    assert "1… d5" in text


def test_puzzle_page_without_a_usable_solution_still_shows_the_board():
    service.puzzle_override = dict(fixture("puzzle.json"), pgn="1. Qz9")
    response = client.get("/puzzle")
    assert response.status_code == 200
    assert response.text.count("data-sq=") == 64
    assert 'id="puzzle-data"' not in response.text
    assert "can't be played here" in response.text


def test_puzzle_page_with_a_broken_fen_is_an_error():
    service.puzzle_override = dict(fixture("puzzle.json"), fen="nonsense")
    assert client.get("/puzzle").status_code == 502


def test_puzzle_title_is_escaped():
    service.puzzle_override = dict(fixture("puzzle.json"), title="</script><script>alert(1)</script>")
    text = client.get("/puzzle").text
    assert "<script>alert(1)" not in text
    assert "&lt;script&gt;alert(1)" in text


@pytest.mark.parametrize("path", ["/streamers", "/puzzle"])
@pytest.mark.parametrize(
    ("error", "status"),
    [(ChessComRateLimitError("slow down"), 429), (ChessComConnectionError("offline"), 502)],
)
def test_streamer_and_puzzle_errors_render_error_page(path, error, status):
    service.error = error
    assert client.get(path).status_code == status


def test_piece_images_and_licence_are_served():
    for code in ("wK", "bQ", "wN", "bP"):
        response = client.get(f"/static/pieces/{code}.svg")
        assert response.status_code == 200
        assert "viewBox" in response.text
    assert "Burnett" in client.get("/static/pieces/LICENSE.txt").text


@pytest.mark.parametrize(
    ("error", "status"),
    [(ChessComRateLimitError("slow down"), 429), (ChessComConnectionError("offline"), 502)],
)
def test_leaderboard_errors_render_error_page(error, status):
    service.error = error
    assert client.get("/leaderboards/blitz").status_code == status
