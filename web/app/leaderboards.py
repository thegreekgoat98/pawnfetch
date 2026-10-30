from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Board:
    slug: str  # used in our URL: /leaderboards/<slug>
    key: str  # chess.com's category name in the /leaderboards response
    label: str
    chip: str  # Tailwind background class for the colour swatch
    score_label: str = "Rating"
    has_record: bool = True  # whether chess.com sends win/loss/draw counts


# Tactics, three-check and battle are left out: their "scores" aren't comparable ratings
# (the tactics board tops out at a capped 65,540).
BOARDS = (
    Board("rapid", "live_rapid", "Rapid", "bg-rapid"),
    Board("blitz", "live_blitz", "Blitz", "bg-blitz"),
    Board("bullet", "live_bullet", "Bullet", "bg-bullet"),
    Board("daily", "daily", "Daily", "bg-daily"),
    Board("blitz960", "live_blitz960", "Chess960", "bg-accent"),
    Board("daily960", "daily960", "Daily 960", "bg-accent"),
    Board("bughouse", "live_bughouse", "Bughouse", "bg-accent"),
    Board("puzzle-rush", "rush", "Puzzle Rush", "bg-accent", "Best score", has_record=False),
)
BOARDS_BY_SLUG = {board.slug: board for board in BOARDS}
DEFAULT_BOARD = "blitz"
