import copy
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from pawnfetch.chesscom.client import PlayerNotFoundError
from pawnfetch.chesscom.models import PlayerProfile, PlayerStats
from web.app.compare import build_sections, tally
from web.app.main import create_app
from web.app.service import PlayerData

FIXTURES = Path(__file__).parent / "fixtures"


def make_player(
    username: str, *, blitz: int | None = None, fide: int | None = None, drop: tuple[str, ...] = ()
) -> PlayerData:
    profile = json.loads((FIXTURES / "profile_hikaru.json").read_text())
    stats = json.loads((FIXTURES / "stats_hikaru.json").read_text())
    profile["username"] = username
    profile["name"] = username.title()
    if blitz is not None:
        stats["chess_blitz"]["last"]["rating"] = blitz
    for key in drop:
        stats.pop(key, None)
    if fide is not None:
        stats["fide"] = fide
    return PlayerData(PlayerProfile.from_api(profile), PlayerStats.from_api(username, copy.deepcopy(stats)))


def row(sections, section_key, label):
    section = next(s for s in sections if s.key == section_key)
    return next(r for r in section.rows if r.label == label)


def test_higher_rating_wins_and_ties_have_no_winner():
    a = make_player("alpha", blitz=3000)
    b = make_player("bravo", blitz=3200)
    sections = build_sections(a, b)

    assert row(sections, "blitz", "Rating").winner == "right"
    assert row(sections, "rapid", "Rating").winner is None  # identical fixtures
    assert row(sections, "blitz", "Games").winner is None  # not a contest


def test_missing_data_shows_dash_without_winner():
    a = make_player("alpha")
    b = make_player("bravo", drop=("fide", "chess_daily"))
    sections = build_sections(a, b)

    fide = row(sections, "more", "FIDE")
    assert (fide.left, fide.right, fide.winner) == ("2,814", "—", None)
    daily = row(sections, "daily", "Rating")
    assert daily.right == "—"
    assert daily.winner is None


def test_zero_fide_means_no_rating():
    assert PlayerStats.from_api("x", {"fide": 0}).fide is None
    sections = build_sections(make_player("alpha"), make_player("bravo", fide=0))
    assert row(sections, "more", "FIDE").right == "—"


def test_tally_counts_rows_won():
    sections = build_sections(make_player("alpha", blitz=3000), make_player("bravo", blitz=3200))
    assert tally(sections) == (0, 1)  # only the blitz rating differs


class FakeService:
    def __init__(self):
        self.players = {
            "alpha": make_player("alpha", blitz=3000),
            "bravo": make_player("bravo", blitz=3200),
        }

    def get_player(self, username: str) -> PlayerData:
        try:
            return self.players[username]
        except KeyError:
            raise PlayerNotFoundError(username) from None

    def close(self) -> None:
        pass


client = TestClient(create_app(FakeService()))


def test_compare_form_page_renders():
    response = client.get("/compare")
    assert response.status_code == 200
    assert "Compare two players" in response.text


def test_compare_query_redirects_to_canonical_url():
    response = client.get("/compare", params={"a": "Alpha", "b": " BRAVO "}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/compare/alpha/bravo"


@pytest.mark.parametrize(
    ("a", "b", "message"),
    [("alpha", "alpha", "two different"), ("alpha", "x", "3-25 characters"), ("<b>", "bravo", "3-25 characters")],
)
def test_compare_rejects_bad_input(a, b, message):
    response = client.get("/compare", params={"a": a, "b": b})
    assert response.status_code == 422
    assert message in response.text


def test_compare_page_renders_both_players():
    response = client.get("/compare/alpha/bravo")
    assert response.status_code == 200
    assert "Alpha" in response.text and "Bravo" in response.text
    assert "3,200" in response.text and "3,000" in response.text


def test_compare_canonicalizes_case_and_same_player():
    upper = client.get("/compare/ALPHA/bravo", follow_redirects=False)
    assert (upper.status_code, upper.headers["location"]) == (308, "/compare/alpha/bravo")
    same = client.get("/compare/alpha/ALPHA", follow_redirects=False)
    assert (same.status_code, same.headers["location"]) == (303, "/player/alpha")


def test_compare_unknown_player_is_404():
    response = client.get("/compare/alpha/ghost")
    assert response.status_code == 404
    assert "ghost" in response.text
