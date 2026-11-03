import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from pawnfetch.chesscom.models import Game
from web.app.openings import opening_name, outcome, summarize

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.chess.com/openings/"


def month() -> list[Game]:
    data = json.loads((FIXTURES / "games_month.json").read_text(encoding="utf-8"))
    return [Game.from_api(g) for g in data["games"]]


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("Caro-Kann-Defense-Exchange-Variation-3...cxd5-4.Nf3", ("Caro-Kann Defense", "Exchange Variation")),
        ("Caro-Kann-Defense-Advance-Short-Variation-with-4-Nf3...e6", ("Caro-Kann Defense", "Advance Short Variation")),
        ("Sicilian-Defense-Open...4.Nxd4-d6", ("Sicilian Defense", "Open")),
        ("Alapin-Sicilian-Defense-2...Nc6-3.Nf3", ("Sicilian Defense", "Alapin Variation")),
        ("Closed-Sicilian-Defense", ("Sicilian Defense", "Closed Variation")),
        ("Queens-Gambit-Declined-Exchange-Variation", ("Queen's Gambit Declined", "Exchange Variation")),
        ("Kings-Pawn-Opening-Kings-Knight-Variation", ("King's Pawn Opening", "King's Knight Variation")),
        ("Modern-Defense-with-1-d4", ("Modern Defense", None)),
        ("Van-t-Kruijs-Opening", ("Van 't Kruijs Opening", None)),
        ("Semi-Slav-Defense-Meran-Variation", ("Semi-Slav Defense", "Meran Variation")),
        ("Englund-Gambit", ("Englund Gambit", None)),
    ],
)
def test_opening_name(slug, expected):
    assert opening_name(URL + slug) == expected


@pytest.mark.parametrize("eco", [None, "", URL + "Undefined", URL + "1.e4"])
def test_opening_name_without_an_opening(eco):
    assert opening_name(eco) is None


@pytest.mark.parametrize(
    ("result", "kind"),
    [("win", "win"), ("agreed", "draw"), ("timevsinsufficient", "draw"), ("checkmated", "loss"), ("abandoned", "loss")],
)
def test_outcome(result, kind):
    assert outcome(result) == kind


def test_summarize_groups_by_colour_and_family():
    summary = summarize("TestPlayer", month(), min_games=2)

    assert summary.games == 8  # the variant, the unnamed and the "Undefined" games are skipped
    italian, sicilian = summary.white
    assert (italian.family, italian.wins, italian.draws, italian.losses) == ("Italian Game", 2, 1, 0)
    assert italian.top_variation == "Two Knights Defense"
    assert round(italian.score) == 83
    assert (sicilian.family, sicilian.games, sicilian.score) == ("Sicilian Defense", 2, 0.0)
    (caro,) = summary.black
    assert (caro.family, caro.wins, caro.draws, caro.losses) == ("Caro-Kann Defense", 1, 1, 1)
    assert caro.top_variation == "Exchange Variation"
    assert summary.first < summary.last


def test_highlights():
    summary = summarize("testplayer", month(), min_games=2)  # username match ignores case
    labels = {h.label: (h.color, h.stats.family) for h in summary.highlights}
    assert labels == {
        "Most played": ("White", "Italian Game"),
        "Best results": ("White", "Italian Game"),
        "Needs work": ("White", "Sicilian Defense"),
    }


def test_best_and_worst_need_enough_games():
    summary = summarize("TestPlayer", month())  # default minimum is 10 games
    assert [h.label for h in summary.highlights] == ["Most played"]


def test_summarize_ignores_other_players_games():
    summary = summarize("someone-else", month())
    assert summary.games == 0
    assert summary.white == summary.black == summary.highlights == []
