"""Turns a chess.com daily puzzle (a FEN plus a PGN solution) into a playable list of moves.

The solution in the PGN is written in SAN ("Nxg6+"), which names a destination square but
not the starting square. To let a visitor play the puzzle by clicking squares, each SAN move
is resolved here into a from-square and to-square, and the board after every move is
recorded. The browser then only compares clicks with these squares; it needs no chess rules.

Only what puzzle solutions need is implemented: resolving legal SAN moves (including pins,
castling, en passant and promotion). It is not a full move generator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FILES = "abcdefgh"
PIECE_NAMES = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight", "P": "pawn"}

KNIGHT_STEPS = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))
KING_STEPS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
STRAIGHTS = ((1, 0), (-1, 0), (0, 1), (0, -1))
SLIDES = {"B": DIAGONALS, "R": STRAIGHTS, "Q": DIAGONALS + STRAIGHTS}

SAN_RE = re.compile(
    r"^(?P<piece>[KQRBN])?(?P<file>[a-h])?(?P<rank>[1-8])?(?P<capture>x)?"
    r"(?P<to>[a-h][1-8])(?:=?(?P<promotion>[QRBN]))?$"
)
RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


class PuzzleError(ValueError):
    """The puzzle's position or solution couldn't be understood."""


def square_name(square: int) -> str:
    return FILES[square % 8] + str(square // 8 + 1)


def parse_square(name: str) -> int:
    if len(name) != 2 or name[0] not in FILES or name[1] not in "12345678":
        raise PuzzleError(f"Not a square: {name!r}")
    return FILES.index(name[0]) + 8 * (int(name[1]) - 1)


def _color(piece: str) -> str:
    return "w" if piece.isupper() else "b"


def _step(square: int, file_step: int, rank_step: int) -> int | None:
    file, rank = square % 8 + file_step, square // 8 + rank_step
    return file + 8 * rank if 0 <= file < 8 and 0 <= rank < 8 else None


def _reaches(board: tuple[str | None, ...], src: int, dst: int, kind: str) -> bool:
    """Whether a non-pawn piece of `kind` on `src` attacks `dst` (sliders stop at blockers)."""
    if kind == "N":
        return any(_step(src, f, r) == dst for f, r in KNIGHT_STEPS)
    if kind == "K":
        return any(_step(src, f, r) == dst for f, r in KING_STEPS)
    for file_step, rank_step in SLIDES[kind]:
        square = _step(src, file_step, rank_step)
        while square is not None:
            if square == dst:
                return True
            if board[square] is not None:
                break
            square = _step(square, file_step, rank_step)
    return False


def _attacked(board: tuple[str | None, ...], square: int, by: str) -> bool:
    forward = 1 if by == "w" else -1
    for src, piece in enumerate(board):
        if piece is None or _color(piece) != by:
            continue
        kind = piece.upper()
        if kind == "P":
            if square in (_step(src, -1, forward), _step(src, 1, forward)):
                return True
        elif _reaches(board, src, square, kind):
            return True
    return False


@dataclass(frozen=True)
class Move:
    src: int
    dst: int
    promotion: str | None = None  # "Q", "R", "B" or "N"
    rook: tuple[int, int] | None = None  # castling: where the rook moves from and to


@dataclass(frozen=True)
class Position:
    board: tuple[str | None, ...]  # 64 squares, index = file + 8 * rank; "N" white, "n" black
    turn: str  # "w" or "b"
    en_passant: int | None = None

    @classmethod
    def from_fen(cls, fen: str) -> Position:
        parts = fen.split()
        if len(parts) < 2:
            raise PuzzleError("A FEN needs at least a board and a side to move.")
        rows = parts[0].split("/")
        if len(rows) != 8:
            raise PuzzleError("A FEN board needs 8 ranks.")
        board: list[str | None] = [None] * 64
        for index, row in enumerate(rows):
            rank, file = 7 - index, 0
            for char in row:
                if char.isdigit():
                    file += int(char)
                elif char.upper() in PIECE_NAMES and file < 8:
                    board[file + 8 * rank] = char
                    file += 1
                else:
                    raise PuzzleError(f"Bad FEN rank: {row!r}")
            if file != 8:
                raise PuzzleError(f"Bad FEN rank: {row!r}")
        if parts[1] not in ("w", "b"):
            raise PuzzleError(f"Bad side to move: {parts[1]!r}")
        en_passant = parse_square(parts[3]) if len(parts) > 3 and parts[3] != "-" else None
        return cls(tuple(board), parts[1], en_passant)

    def placement(self) -> str:
        """The board part of a FEN, e.g. "rnbqkbnr/pppppppp/8/..."."""
        rows = []
        for rank in range(7, -1, -1):
            row, empty = "", 0
            for file in range(8):
                piece = self.board[file + 8 * rank]
                if piece is None:
                    empty += 1
                    continue
                if empty:
                    row, empty = row + str(empty), 0
                row += piece
            rows.append(row + (str(empty) if empty else ""))
        return "/".join(rows)

    def play(self, move: Move) -> Position:
        board = list(self.board)
        piece = board[move.src]
        if piece is None:
            raise PuzzleError(f"No piece on {square_name(move.src)}.")
        if piece.upper() == "P" and move.dst == self.en_passant and board[move.dst] is None:
            board[move.dst - 8 if self.turn == "w" else move.dst + 8] = None
        if move.promotion:
            piece = move.promotion if self.turn == "w" else move.promotion.lower()
        board[move.dst], board[move.src] = piece, None
        if move.rook:
            rook_src, rook_dst = move.rook
            board[rook_dst], board[rook_src] = board[rook_src], None
        en_passant = None
        if piece.upper() == "P" and abs(move.dst - move.src) == 16:
            en_passant = (move.src + move.dst) // 2
        return Position(tuple(board), "b" if self.turn == "w" else "w", en_passant)

    def parse_san(self, san: str) -> Move:
        text = san.strip().replace("e.p.", "").rstrip("+#!?")
        if text in ("O-O", "0-0", "O-O-O", "0-0-0"):
            return self._castle(long=text.count("-") == 2)

        match = SAN_RE.match(text)
        if not match:
            raise PuzzleError(f"Not a move: {san!r}")
        kind = match["piece"] or "P"
        dst = parse_square(match["to"])
        target = self.board[dst]
        if target is not None and _color(target) == self.turn:
            raise PuzzleError(f"{san!r} would capture its own piece.")

        candidates = []
        for src, piece in enumerate(self.board):
            if piece is None or _color(piece) != self.turn or piece.upper() != kind:
                continue
            if match["file"] and src % 8 != FILES.index(match["file"]):
                continue
            if match["rank"] and src // 8 != int(match["rank"]) - 1:
                continue
            if kind == "P":
                if not self._pawn_reaches(src, dst, capture=bool(match["capture"])):
                    continue
            elif not _reaches(self.board, src, dst, kind):
                continue
            move = Move(src, dst, match["promotion"])
            if self._king_safe_after(move):
                candidates.append(move)

        if len(candidates) != 1:
            raise PuzzleError(f"Can't tell which piece plays {san!r}.")
        move = candidates[0]
        last_rank = 7 if self.turn == "w" else 0
        promotes = kind == "P" and dst // 8 == last_rank
        if promotes != bool(move.promotion):
            raise PuzzleError(f"Bad promotion in {san!r}.")
        return move

    def _pawn_reaches(self, src: int, dst: int, capture: bool) -> bool:
        forward = 8 if self.turn == "w" else -8
        if capture:
            diagonal = dst - src in (forward - 1, forward + 1) and abs(dst % 8 - src % 8) == 1
            return diagonal and (self.board[dst] is not None or dst == self.en_passant)
        if self.board[dst] is not None:
            return False
        if dst - src == forward:
            return True
        start_rank = 1 if self.turn == "w" else 6
        return (
            dst - src == 2 * forward
            and src // 8 == start_rank
            and self.board[src + forward] is None
        )

    def _castle(self, long: bool) -> Move:
        base = 0 if self.turn == "w" else 56
        king, rook = ("K", "R") if self.turn == "w" else ("k", "r")
        rook_src = base + (0 if long else 7)
        between = range(base + 1, base + 4) if long else range(base + 5, base + 7)
        king_path = (base + 4, base + 3, base + 2) if long else (base + 4, base + 5, base + 6)
        enemy = "b" if self.turn == "w" else "w"
        if (
            self.board[base + 4] != king
            or self.board[rook_src] != rook
            or any(self.board[square] is not None for square in between)
            or any(_attacked(self.board, square, enemy) for square in king_path)
        ):
            raise PuzzleError("Castling isn't possible here.")
        return Move(base + 4, base + (2 if long else 6), rook=(rook_src, base + (3 if long else 5)))

    def _king_safe_after(self, move: Move) -> bool:
        after = self.play(move)
        king = "K" if self.turn == "w" else "k"
        if king not in after.board:
            return True  # some composed positions have no king; nothing to protect
        return not _attacked(after.board, after.board.index(king), after.turn)


def solution_moves(pgn: str) -> list[str]:
    """The main-line SAN moves of a PGN, without headers, comments, variations or numbers."""
    text = re.sub(r"^\s*\[[^\]]*\]\s*$", " ", pgn, flags=re.MULTILINE)
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = re.sub(r";[^\n]*", " ", text)
    previous = None
    while previous != text:  # remove (variations), innermost first
        previous, text = text, re.sub(r"\([^()]*\)", " ", text)
    text = re.sub(r"\$\d+", " ", text)
    text = re.sub(r"\d+\.(?:\.\.)?", " ", text)
    return [token for token in text.split() if token not in RESULTS]


@dataclass(frozen=True)
class Step:
    src: str
    dst: str
    san: str
    board: str  # FEN placement after the move
    promotion: str | None = None


@dataclass(frozen=True)
class Solution:
    start: str  # FEN placement before the first move
    solver: str  # "w" or "b": the side the visitor plays
    steps: tuple[Step, ...]

    def as_json(self) -> dict:
        return {
            "start": self.start,
            "solver": self.solver,
            "steps": [
                {"from": s.src, "to": s.dst, "san": s.san, "board": s.board, "promotion": s.promotion}
                for s in self.steps
            ],
        }


def solve(fen: str, pgn: str) -> Solution:
    position = Position.from_fen(fen)
    start, solver = position.placement(), position.turn
    steps = []
    for san in solution_moves(pgn):
        move = position.parse_san(san)
        position = position.play(move)
        steps.append(
            Step(square_name(move.src), square_name(move.dst), san, position.placement(), move.promotion)
        )
    if not steps:
        raise PuzzleError("The puzzle has no solution moves.")
    return Solution(start, solver, tuple(steps))


def numbered(sans: list[str], first: str) -> list[str]:
    """SAN moves with move numbers, e.g. ["1. Nxg6+", "hxg6", "2. Qh4#"]."""
    out, number, color = [], 1, first
    for index, san in enumerate(sans):
        if color == "w":
            out.append(f"{number}. {san}")
        else:
            out.append(f"{number}… {san}" if index == 0 else san)
            number += 1
        color = "b" if color == "w" else "w"
    return out


@dataclass(frozen=True)
class Square:
    name: str
    piece: str | None  # e.g. "wN"
    light: bool
    file_label: str | None  # shown on the bottom row
    rank_label: str | None  # shown on the left column

    @property
    def label(self) -> str:
        if not self.piece:
            return self.name
        color = "white" if self.piece[0] == "w" else "black"
        return f"{self.name}, {color} {PIECE_NAMES[self.piece[1]]}"


def board_squares(placement: str, orientation: str) -> list[Square]:
    """The 64 squares in display order, top-left first, for the side at the bottom."""
    board = Position.from_fen(f"{placement} w").board
    ranks = range(7, -1, -1) if orientation == "w" else range(8)
    files = list(range(8)) if orientation == "w" else list(range(7, -1, -1))
    squares = []
    for row, rank in enumerate(ranks):
        for column, file in enumerate(files):
            index = file + 8 * rank
            piece = board[index]
            squares.append(
                Square(
                    name=square_name(index),
                    piece=f"{_color(piece)}{piece.upper()}" if piece else None,
                    light=(file + rank) % 2 == 1,
                    file_label=FILES[file] if row == 7 else None,
                    rank_label=str(rank + 1) if column == 0 else None,
                )
            )
    return squares
