import pytest

pytest.importorskip("fastapi")

from web.app.puzzle import numbered, side_to_move, solution_moves


def test_real_daily_puzzle_moves():
    pgn = (
        '[White "G32Games"]\n[Black "Daily Puzzle Inspiration"]\n[Result "1-0"]\n'
        '[FEN "2r1nr1k/1bp3qp/1p4p1/p4p2/PnBQ1N2/1P5P/1BP2RP1/6K1 w - - 0 1"]\n\n'
        "1. Nxg6+ hxg6 2. Qh4# 1-0"
    )
    assert solution_moves(pgn) == ["Nxg6+", "hxg6", "Qh4#"]


def test_windows_line_endings_and_star_result():
    pgn = '[Date "????.??.??"]\r\n[Result "*"]\r\n\r\n1. Nf7+ Kd7 2. Qg4# \r\n*'
    assert solution_moves(pgn) == ["Nf7+", "Kd7", "Qg4#"]


def test_black_to_move_numbering():
    assert solution_moves("1... d5 2. exd6") == ["d5", "exd6"]


def test_comments_variations_and_nags_are_ignored():
    pgn = '[Event "x"]\n\n1. e4 {best by test} e5 (1... c5 2. Nf3 (2. c3)) 2. Nf3 $1 Nc6 *'
    assert solution_moves(pgn) == ["e4", "e5", "Nf3", "Nc6"]


def test_empty_pgn_has_no_moves():
    assert solution_moves("") == []


def test_numbered_moves():
    assert numbered(["Nxg6+", "hxg6", "Qh4#"], "w") == ["1. Nxg6+", "hxg6", "2. Qh4#"]
    assert numbered(["d5", "exd6"], "b") == ["1… d5", "2. exd6"]


@pytest.mark.parametrize(
    ("fen", "side"),
    [("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "w"), ("4k3/8/8/8/8/8/8/4K3 b - -", "b"), ("nonsense", "w")],
)
def test_side_to_move(fen, side):
    assert side_to_move(fen) == side
