import io
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from web.app.puzzles import (
    LEVELS_BY_SLUG,
    Puzzle,
    PuzzleBank,
    PuzzlesUnavailableError,
    build,
    main,
    read_rows,
    theme_label,
)

FIXTURE = Path(__file__).parent / "fixtures" / "puzzles.csv"


@pytest.fixture
def bank(tmp_path) -> PuzzleBank:
    path = tmp_path / "puzzles.sqlite"
    with FIXTURE.open(encoding="utf-8", newline="") as text:
        build(read_rows(text), path)
    return PuzzleBank(path)


def test_filter_keeps_popular_puzzles_only():
    with FIXTURE.open(encoding="utf-8", newline="") as text:
        ids = [row[0] for row in read_rows(text)]
    assert "004b0" not in ids  # popularity 47, 36 plays
    assert len(ids) == 7


def test_unexpected_header_is_rejected():
    with pytest.raises(ValueError, match="header"):
        list(read_rows(io.StringIO("a,b,c\n1,2,3\n")))


def test_build_numbers_rows_in_rating_order(bank):
    with sqlite3.connect(bank.path) as db:
        ratings = [r for (r,) in db.execute("SELECT rating FROM puzzles ORDER BY num")]
        nums = [n for (n,) in db.execute("SELECT num FROM puzzles ORDER BY num")]
    assert ratings == sorted(ratings)
    assert nums == list(range(1, len(nums) + 1))
    assert not bank.path.with_name(bank.path.name + ".tmp").exists()


def test_build_caps_each_level(tmp_path):
    with FIXTURE.open(encoding="utf-8", newline="") as text:
        counts = build(read_rows(text), tmp_path / "p.sqlite", per_level=1)
    assert counts == {"easy": 1, "medium": 1, "hard": 1}


def test_get_returns_a_parsed_puzzle(bank):
    puzzle = bank.get("00008")
    assert puzzle == Puzzle(
        id="00008",
        fen="r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2R1/PqP2bPP/7K b - - 0 24",
        moves=("f2g3", "e6e7", "b2b1", "b3c1", "b1c1", "h6c1"),
        rating=1811,
        themes=("crushing", "hangingPiece", "long", "middlegame"),
        game_url="https://lichess.org/787zsVup/black#48",
    )
    assert puzzle.solver == "w"  # black moves first, the visitor answers as white
    assert puzzle.level.slug == "medium"
    assert puzzle.tags == ["Crushing", "Hanging piece", "Middlegame"]  # "long" is hidden
    assert bank.get("zzzzz") is None


@pytest.mark.parametrize("slug", ["easy", "medium", "hard"])
def test_random_stays_inside_the_level(bank, slug):
    level = LEVELS_BY_SLUG[slug]
    for _ in range(20):
        puzzle = bank.random(level)
        assert level.low <= puzzle.rating < level.high


def test_missing_database_is_unavailable(tmp_path):
    bank = PuzzleBank(tmp_path / "nope.sqlite")
    with pytest.raises(PuzzlesUnavailableError):
        bank.random(LEVELS_BY_SLUG["easy"])
    with pytest.raises(PuzzlesUnavailableError):
        bank.get("00008")


def test_corrupt_database_is_unavailable(tmp_path):
    path = tmp_path / "broken.sqlite"
    path.write_bytes(b"not a database")
    with pytest.raises(PuzzlesUnavailableError):
        PuzzleBank(path).get("00008")


@pytest.mark.parametrize(
    ("theme", "label"),
    [("mateIn2", "Mate in 2"), ("backRankMate", "Back rank mate"), ("fork", "Fork")],
)
def test_theme_label(theme, label):
    assert theme_label(theme) == label


def test_import_command_from_a_local_file(tmp_path, capsys):
    path = tmp_path / "out.sqlite"
    assert main(["import", "--source", str(FIXTURE), "--db", str(path)]) == 0
    assert "Wrote 7 puzzles" in capsys.readouterr().out
    assert PuzzleBank(path).get("001wr") is not None
