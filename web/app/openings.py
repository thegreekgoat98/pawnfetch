"""Opening statistics for the player page, built from a player's recent chess.com games.

chess.com names each game's opening in its "eco" URL, e.g.
https://www.chess.com/openings/Caro-Kann-Defense-Exchange-Variation-3...cxd5-4.Nf3
Those names are very specific, so games are grouped by opening family ("Caro-Kann Defense")
and the most common variation within each family is shown alongside it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from pawnfetch.chesscom.models import Game

# A family name ends at the first of these words: "Sicilian Defense", "Italian Game", ...
FAMILY_ENDS = {"Defense", "Defence", "Opening", "Game", "Gambit", "System", "Attack"}
# Words that only make sense with what follows them; dropped if a name is cut off after them.
DANGLING = {"with", "and", "the", "of", "in"}
# The URLs drop apostrophes and turn hyphens into word breaks; put the common ones back.
WORD_FIXES = {
    "Alekhines": "Alekhine's",
    "Birds": "Bird's",
    "Bishops": "Bishop's",
    "Damianos": "Damiano's",
    "Kings": "King's",
    "Larsens": "Larsen's",
    "Owens": "Owen's",
    "Petrovs": "Petrov's",
    "Queens": "Queen's",
}
PHRASE_FIXES = {
    "Caro Kann": "Caro-Kann",
    "Nimzo Indian": "Nimzo-Indian",
    "Bogo Indian": "Bogo-Indian",
    "Nimzo Larsen": "Nimzo-Larsen",
    "Nimzowitsch Larsen": "Nimzowitsch-Larsen",
    "Semi Slav": "Semi-Slav",
    "Neo Grunfeld": "Neo-Grünfeld",
    "Grunfeld": "Grünfeld",
    "Richter Veresov": "Richter-Veresov",
    "Mieses Kotrc": "Mieses-Kotrc",
    "Van t Kruijs": "Van 't Kruijs",
}
# chess.com files a few variations as their own opening; put them back under the family.
FAMILY_ALIASES = {
    "Alapin Sicilian Defense": ("Sicilian Defense", "Alapin Variation"),
    "Closed Sicilian Defense": ("Sicilian Defense", "Closed Variation"),
}

DRAWS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def opening_name(eco_url: str | None) -> tuple[str, str | None] | None:
    """(family, variation) from a chess.com opening URL, or None if it doesn't name one."""
    if not eco_url:
        return None
    words: list[str] = []
    for token in eco_url.rstrip("/").rsplit("/", 1)[-1].split("-"):
        head, dots, _ = token.partition("...")  # "Open...4.Nxd4": the moves start after "..."
        if any(ch.isdigit() for ch in head):  # "3.Nf3", "2", "1": moves or move numbers
            break
        if head:
            words.append(WORD_FIXES.get(head, head))
        if dots:
            break
    while words and words[-1].lower() in DANGLING:
        words.pop()
    if not words or words == ["Undefined"]:
        return None
    end = next((i + 1 for i, word in enumerate(words) if word in FAMILY_ENDS), len(words))
    if words[end - 1] == "Gambit" and end < len(words) and words[end] in ("Accepted", "Declined"):
        end += 1
    family, variation = _fix(" ".join(words[:end])), _fix(" ".join(words[end:]))
    if family in FAMILY_ALIASES:
        family, alias = FAMILY_ALIASES[family]
        variation = f"{alias} {variation}".strip()
    return family, variation or None


def _fix(text: str) -> str:
    for wrong, right in PHRASE_FIXES.items():
        text = text.replace(wrong, right)
    return text


def outcome(result: str) -> str:
    """"win", "draw" or "loss" from a chess.com result code ("checkmated", "agreed", ...)."""
    if result == "win":
        return "win"
    return "draw" if result in DRAWS else "loss"


@dataclass
class OpeningStats:
    family: str
    wins: int = 0
    draws: int = 0
    losses: int = 0
    variations: Counter = field(default_factory=Counter)

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def score(self) -> float:
        """Points per game as a percentage: a draw counts half, like a tournament score."""
        return (self.wins + self.draws / 2) / self.games * 100 if self.games else 0.0

    @property
    def win_pct(self) -> float:
        return self.wins / self.games * 100 if self.games else 0.0

    @property
    def draw_pct(self) -> float:
        return self.draws / self.games * 100 if self.games else 0.0

    @property
    def top_variation(self) -> str | None:
        named = [name for name, _ in self.variations.most_common() if name]
        return named[0] if named else None

    def add(self, result: str, variation: str | None) -> None:
        kind = outcome(result)
        if kind == "win":
            self.wins += 1
        elif kind == "draw":
            self.draws += 1
        else:
            self.losses += 1
        self.variations[variation] += 1


@dataclass
class Highlight:
    label: str  # "Most played", "Best results" or "Needs work"
    color: str  # "White" or "Black"
    stats: OpeningStats


@dataclass
class OpeningsSummary:
    games: int  # games with a known opening that were counted
    first: datetime | None
    last: datetime | None
    white: list[OpeningStats]
    black: list[OpeningStats]
    highlights: list[Highlight]


def summarize(username: str, games: list[Game], top: int = 5, min_games: int = 10) -> OpeningsSummary:
    """Opening families per colour, most-played first, plus favourite/best/worst highlights.

    Only standard chess games with a named opening count. Best and worst need at least
    `min_games` games so that one lucky win doesn't top the list.
    """
    me = username.strip().lower()
    by_color: dict[str, dict[str, OpeningStats]] = {"white": {}, "black": {}}
    times: list[datetime] = []
    counted = 0
    for game in games:
        name = opening_name(game.eco_url)
        if game.rules != "chess" or name is None:
            continue
        if game.white.username.lower() == me:
            side = "white"
        elif game.black.username.lower() == me:
            side = "black"
        else:
            continue
        family, variation = name
        stats = by_color[side].setdefault(family, OpeningStats(family))
        stats.add(getattr(game, side).result, variation)
        counted += 1
        if game.end_time:
            times.append(game.end_time)

    def ranked(side: str) -> list[OpeningStats]:
        return sorted(by_color[side].values(), key=lambda s: (-s.games, -s.score, s.family))

    white, black = ranked("white"), ranked("black")
    everything = [("White", s) for s in white] + [("Black", s) for s in black]
    regular = [(color, s) for color, s in everything if s.games >= min_games]
    highlights = []
    if everything:
        color, stats = max(everything, key=lambda cs: (cs[1].games, cs[1].score))
        highlights.append(Highlight("Most played", color, stats))
    if len(regular) >= 2:
        color, best = max(regular, key=lambda cs: (cs[1].score, cs[1].games))
        highlights.append(Highlight("Best results", color, best))
        color, worst = min(regular, key=lambda cs: (cs[1].score, -cs[1].games))
        if worst is not best:
            highlights.append(Highlight("Needs work", color, worst))

    return OpeningsSummary(
        games=counted,
        first=min(times) if times else None,
        last=max(times) if times else None,
        white=white[:top],
        black=black[:top],
        highlights=highlights,
    )
