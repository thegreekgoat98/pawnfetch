import pytest

pytest.importorskip("fastapi")

from web.app.puzzle import (
    Position,
    PuzzleError,
    board_squares,
    numbered,
    solution_moves,
    solve,
)

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_real_daily_puzzle():
    fen = "2r1nr1k/1bp3qp/1p4p1/p4p2/PnBQ1N2/1P5P/1BP2RP1/6K1 w - - 0 1"
    pgn = (
        '[White "G32Games"]\n[Black "Daily Puzzle Inspiration"]\n[Result "1-0"]\n'
        f'[FEN "{fen}"]\n\n1. Nxg6+ hxg6 2. Qh4# 1-0'
    )

    solution = solve(fen, pgn)

    assert solution.solver == "w"
    assert [(s.src, s.dst) for s in solution.steps] == [("f4", "g6"), ("h7", "g6"), ("d4", "h4")]
    assert solution.steps[-1].board == "2r1nr1k/1bp3q1/1p4p1/p4p2/PnB4Q/1P5P/1BP2RP1/6K1"


def test_real_puzzle_with_windows_line_endings():
    fen = "r1bkr3/ppp1b1Qp/2n5/4p1N1/4n3/2Pq4/PP1P2PP/RNB1KR2 w Q - 0 1"
    pgn = f'[Date "????.??.??"]\r\n[Result "*"]\r\n[FEN "{fen}"]\r\n\r\n1. Nf7+ Kd7 2. Qg4# \r\n*'

    steps = solve(fen, pgn).steps

    assert [(s.src, s.dst) for s in steps] == [("g5", "f7"), ("d8", "d7"), ("g7", "g4")]


def test_black_to_move_and_en_passant():
    solution = solve("4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1", "1... d5 2. exd6")

    assert solution.solver == "b"
    assert solution.steps[1].dst == "d6"
    assert solution.steps[1].board == "4k3/8/3P4/8/8/8/8/4K3"  # the d5 pawn was captured


def test_castling_both_ways():
    steps = solve("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "1. O-O O-O-O").steps

    assert (steps[0].src, steps[0].dst) == ("e1", "g1")
    assert (steps[1].src, steps[1].dst) == ("e8", "c8")
    assert steps[1].board == "2kr3r/8/8/8/8/8/8/R4RK1"


def test_cannot_castle_through_check():
    with pytest.raises(PuzzleError):
        solve("4k3/8/8/8/8/8/5r2/4K2R w K - 0 1", "1. O-O")  # f1 is attacked by the f2 rook


def test_promotion_with_capture():
    step = solve("3r3k/4P3/8/8/8/8/8/4K3 w - - 0 1", "1. exd8=Q+").steps[0]

    assert step.promotion == "Q"
    assert step.board == "3Q3k/8/8/8/8/8/8/4K3"


def test_pawn_reaching_last_rank_must_promote():
    with pytest.raises(PuzzleError):
        solve("7k/4P3/8/8/8/8/8/4K3 w - - 0 1", "1. e8")


def test_disambiguation_by_file_and_rank():
    knights = "7k/8/8/8/8/8/8/1N2KN2 w - - 0 1"
    assert solve(knights, "Nbd2").steps[0].src == "b1"
    with pytest.raises(PuzzleError, match="which piece"):
        solve(knights, "Nd2")

    rooks = "7k/8/8/R7/8/8/8/R3K3 w - - 0 1"
    assert solve(rooks, "R1a3").steps[0].src == "a1"


def test_pinned_piece_is_not_a_candidate():
    # Both knights reach e4, but the c3 knight is pinned to the king by the a5 bishop.
    assert solve("8/8/8/b7/8/2N3N1/8/4K2k w - - 0 1", "Ne4").steps[0].src == "g3"


def test_pgn_comments_variations_and_nags_are_ignored():
    pgn = '[Event "x"]\n\n1. e4 {best by test} e5 (1... c5 2. Nf3 (2. c3)) 2. Nf3 $1 Nc6 *'

    assert solution_moves(pgn) == ["e4", "e5", "Nf3", "Nc6"]
    assert len(solve(START, pgn).steps) == 4


@pytest.mark.parametrize("pgn", ["", "1. Ke7", "1. Qh5", "1. e5", "1. Nxe4", "1. O-O", "1. zz"])
def test_bad_solutions_raise(pgn):
    with pytest.raises(PuzzleError):
        solve(START, pgn)


@pytest.mark.parametrize(
    "fen", ["", "8/8/8 w", "9/8/8/8/8/8/8/8 w", "8/8/8/8/8/8/8/7x w", "8/8/8/8/8/8/8/8 x"]
)
def test_bad_fens_raise(fen):
    with pytest.raises(PuzzleError):
        Position.from_fen(fen)


def test_placement_round_trips():
    assert Position.from_fen(START).placement() == START.split()[0]


def test_numbered_moves():
    assert numbered(["Nxg6+", "hxg6", "Qh4#"], "w") == ["1. Nxg6+", "hxg6", "2. Qh4#"]
    assert numbered(["d5", "exd6"], "b") == ["1… d5", "2. exd6"]


def test_board_squares_follow_orientation():
    white = board_squares(START.split()[0], "w")
    black = board_squares(START.split()[0], "b")

    assert [white[0].name, white[63].name] == ["a8", "h1"]
    assert [black[0].name, black[63].name] == ["h1", "a8"]
    assert white[0].piece == "bR" and white[0].light  # a8 and h1 are light squares
    assert not white[56].light  # a1 is dark
    assert (white[56].file_label, white[56].rank_label) == ("a", "1")
    assert (black[56].file_label, black[56].rank_label) == ("h", "8")
    assert white[0].label == "a8, black rook" and white[20].label == "e6"
