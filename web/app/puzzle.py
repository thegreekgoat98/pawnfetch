"""Small helpers for the daily puzzle page.

The chess rules (legal moves, check, mate) run in the browser with chess.js, so the server
only needs to pull the solution moves out of chess.com's PGN text and say whose turn it is.
"""

from __future__ import annotations

import re

RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


def side_to_move(fen: str) -> str:
    """"w" or "b" from a FEN; white if the FEN doesn't say."""
    parts = fen.split()
    return parts[1] if len(parts) > 1 and parts[1] in ("w", "b") else "w"


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
