"""Past games between two players, found in one player's recent games."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pawnfetch.chesscom.models import Game
from web.app.openings import outcome

RECENT_MEETINGS = 5


@dataclass
class Meeting:
    url: str
    outcome: str  # for the player whose games were searched: "win", "draw" or "loss"
    time_class: str
    end_time: datetime | None


def index_meetings(username: str, games: list[Game]) -> dict[str, list[Meeting]]:
    """Each opponent (lower-case username) -> games against them, newest first."""
    me = username.strip().lower()
    meetings: dict[str, list[Meeting]] = {}
    for game in games:
        if game.white.username.lower() == me:
            mine, theirs = game.white, game.black
        elif game.black.username.lower() == me:
            mine, theirs = game.black, game.white
        else:
            continue
        meetings.setdefault(theirs.username.lower(), []).append(
            Meeting(game.url, outcome(mine.result), game.time_class, game.end_time)
        )
    for found in meetings.values():
        found.sort(key=lambda m: m.end_time.timestamp() if m.end_time else 0, reverse=True)
    return meetings


@dataclass
class HeadToHead:
    wins: int
    draws: int
    losses: int
    recent: list[Meeting]  # newest first

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses


def head_to_head(meetings: list[Meeting]) -> HeadToHead:
    return HeadToHead(
        wins=sum(m.outcome == "win" for m in meetings),
        draws=sum(m.outcome == "draw" for m in meetings),
        losses=sum(m.outcome == "loss" for m in meetings),
        recent=meetings[:RECENT_MEETINGS],
    )
