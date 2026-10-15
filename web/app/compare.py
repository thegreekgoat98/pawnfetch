from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from web.app.filters import intcomma
from web.app.service import PlayerData

MODES = (("rapid", "Rapid"), ("blitz", "Blitz"), ("bullet", "Bullet"), ("daily", "Daily"))


@dataclass
class CompareRow:
    label: str
    left: str
    right: str
    winner: str | None  # "left", "right" or None


@dataclass
class CompareSection:
    key: str
    title: str
    rows: list[CompareRow]


def _row(
    label: str,
    left: float | None,
    right: float | None,
    fmt: Callable[[float], str] = intcomma,
    competitive: bool = True,
) -> CompareRow:
    winner = None
    if competitive and left is not None and right is not None and left != right:
        winner = "left" if left > right else "right"
    return CompareRow(
        label,
        "—" if left is None else fmt(left),
        "—" if right is None else fmt(right),
        winner,
    )


def _pct(value: float) -> str:
    return f"{value:.0f}%"


def build_sections(a: PlayerData, b: PlayerData) -> list[CompareSection]:
    sections: list[CompareSection] = []
    for key, title in MODES:
        sa, sb = getattr(a.stats, key), getattr(b.stats, key)
        if sa is None and sb is None:
            continue
        sections.append(
            CompareSection(
                key,
                title,
                [
                    _row("Rating", sa and sa.rating, sb and sb.rating),
                    _row("Peak", sa and sa.best_rating, sb and sb.best_rating),
                    _row(
                        "Win rate",
                        sa.win_pct if sa and sa.total else None,
                        sb.win_pct if sb and sb.total else None,
                        _pct,
                    ),
                    _row("Games", sa and sa.total, sb and sb.total, competitive=False),
                ],
            )
        )

    sections.append(
        CompareSection(
            "more",
            "More",
            [
                _row("FIDE", a.stats.fide, b.stats.fide),
                _row(
                    "Puzzle Rush",
                    a.stats.puzzle_rush and a.stats.puzzle_rush.score,
                    b.stats.puzzle_rush and b.stats.puzzle_rush.score,
                ),
                _row("Tactics peak", a.stats.tactics_highest, b.stats.tactics_highest),
                _row("Followers", a.profile.followers, b.profile.followers),
            ],
        )
    )
    return sections


def tally(sections: list[CompareSection]) -> tuple[int, int]:
    rows = [row for section in sections for row in section.rows]
    return (
        sum(row.winner == "left" for row in rows),
        sum(row.winner == "right" for row in rows),
    )
