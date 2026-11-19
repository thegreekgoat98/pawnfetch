"""The "roast" card: a persona and a few teasing lines built from a player's recent games.

Everything here is rule-based. Each trait gets a score (roughly 0-1, higher means more
extreme); the card shows the strongest traits, and the strongest one names the persona.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import pairwise

from pawnfetch.chesscom.models import Game
from web.app.openings import opening_name, outcome

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MIN_GAMES = 20  # fewer standard games than this and there's nothing to roast
MAX_LINES = 4
MIN_SAMPLE = 15  # games behind a percentage before it's quoted
REVENGE_GAP = timedelta(minutes=2)
MODE_NAMES = {"bullet": "Bullet", "blitz": "Blitz", "rapid": "Rapid", "daily": "Daily"}
DEFAULT_PERSONA = "Perfectly Balanced Enjoyer"


@dataclass
class Roast:
    persona: str
    lines: list[str]
    games: int
    win_pct: float
    main_mode: str  # "Blitz", ...
    first: datetime | None
    last: datetime | None


@dataclass
class _Trait:
    score: float
    persona: str
    line: str


@dataclass
class _Played:
    game: Game
    me: str  # my chess.com result code
    opp: str  # opponent's result code
    out: str  # "win", "draw" or "loss"
    rating: int | None


def _pct(part: float, whole: float) -> str:
    return f"{part / whole * 100:.0f}%"


def _short_family(family: str) -> str:
    """"Caro-Kann Defense" -> "Caro-Kann", for the persona name."""
    for suffix in (" Defense", " Defence", " Opening", " Game", " Gambit", " System", " Attack"):
        if family.endswith(suffix):
            return family[: -len(suffix)]
    return family


def build_roast(username: str, games: list[Game]) -> Roast | None:
    me = username.strip().lower()
    played: list[_Played] = []
    for game in sorted(games, key=lambda g: g.end_time or EPOCH):
        if game.rules != "chess":
            continue
        if game.white.username.lower() == me:
            mine, theirs = game.white, game.black
        elif game.black.username.lower() == me:
            mine, theirs = game.black, game.white
        else:
            continue
        played.append(_Played(game, mine.result, theirs.result, outcome(mine.result), mine.rating))
    if len(played) < MIN_GAMES:
        return None

    traits = [t for t in _traits(me, played) if t is not None]
    traits.sort(key=lambda t: t.score, reverse=True)
    picked = [t for t in traits if t.score >= 0.3][:MAX_LINES]
    for filler in _fillers(played):
        if len(picked) >= 3:
            break
        picked.append(filler)

    modes = Counter(p.game.time_class for p in played)
    times = [p.game.end_time for p in played if p.game.end_time]
    wins = sum(p.out == "win" for p in played)
    return Roast(
        persona=picked[0].persona if picked[0].score >= 0.3 else DEFAULT_PERSONA,
        lines=[t.line for t in picked],
        games=len(played),
        win_pct=wins / len(played) * 100,
        main_mode=MODE_NAMES.get(modes.most_common(1)[0][0], "Chess"),
        first=min(times, default=None),
        last=max(times, default=None),
    )


def _traits(me: str, played: list[_Played]) -> list[_Trait | None]:
    return [
        _time_control(played),
        _first_move(me, played),
        _black_defence(me, played),
        _flagged(played),
        _flagger(played),
        _resigning(played),
        _abandons(played),
        _tilt(played),
        _revenge(played),
        _streaks(played),
        _quick_mate(played),
        _rating_trend(played),
        _draws(played),
        _win_rate(played),
    ]


def _time_control(played: list[_Played]) -> _Trait | None:
    mode, count = Counter(p.game.time_class for p in played).most_common(1)[0]
    share = count / len(played)
    p = _pct(count, len(played))
    if mode == "bullet" and share >= 0.5:
        return _Trait(share, "Caffeinated Bullet Goblin", f"{p} of games are bullet. Thinking is clearly optional.")
    if mode == "rapid" and share >= 0.6:
        return _Trait(share * 0.7, "Rapid Philosopher", f"{p} rapid. Needs ten whole minutes to blunder properly.")
    if mode == "daily" and share >= 0.5:
        return _Trait(share * 0.7, "Correspondence Snail", f"{p} daily chess. One move a day, still finds the blunder.")
    return None


def _first_move(me: str, played: list[_Played]) -> _Trait | None:
    moves = Counter(p.game.first_move for p in played if p.game.white.username.lower() == me and p.game.first_move)
    total = sum(moves.values())
    if total < MIN_SAMPLE:
        return None
    move, count = moves.most_common(1)[0]
    share = count / total
    if move not in ("e4", "d4", "Nf3", "c4") and share >= 0.4:
        return _Trait(0.8, "Offbeat Opening Hipster", f"Opens 1.{move} {_pct(count, total)} of the time. Bold. Questionable, but bold.")
    if share >= 0.75:
        persona = {"e4": "1.e4 Loyalist", "d4": "1.d4 Bureaucrat"}.get(move, f"1.{move} Purist")
        return _Trait(share, persona, f"1.{move} in {_pct(count, total)} of White games. Variety is for cowards.")
    return None


def _black_defence(me: str, played: list[_Played]) -> _Trait | None:
    families: Counter = Counter()
    for p in played:
        name = opening_name(p.game.eco_url)
        if p.game.black.username.lower() == me and name:
            families[name[0]] += 1
    total = sum(families.values())
    if total < MIN_SAMPLE:
        return None
    family, count = families.most_common(1)[0]
    share = count / total
    if share < 0.5:
        return None
    return _Trait(
        share * 0.9,
        f"{_short_family(family)} Monk",
        f"Plays the {family} in {_pct(count, total)} of Black games. Commitment issues: none.",
    )


def _losses(played: list[_Played]) -> list[_Played]:
    return [p for p in played if p.out == "loss"]


def _flagged(played: list[_Played]) -> _Trait | None:
    losses = _losses(played)
    timeouts = sum(p.me == "timeout" for p in losses)
    if len(losses) < MIN_SAMPLE or timeouts / len(losses) < 0.25:
        return None
    return _Trait(
        min(1.0, timeouts / len(losses) * 1.6),
        "Professional Flag Victim",
        f"{_pct(timeouts, len(losses))} of losses are on time. The clock is the real opponent.",
    )


def _flagger(played: list[_Played]) -> _Trait | None:
    wins = [p for p in played if p.out == "win"]
    flags = sum(p.opp == "timeout" for p in wins)
    if len(wins) < MIN_SAMPLE or flags / len(wins) < 0.25:
        return None
    return _Trait(
        min(1.0, flags / len(wins) * 1.6),
        "Clock Assassin",
        f"{_pct(flags, len(wins))} of wins come from the opponent's clock. Who needs checkmate?",
    )


def _resigning(played: list[_Played]) -> _Trait | None:
    losses = _losses(played)
    if len(losses) < MIN_SAMPLE:
        return None
    resigned = [p for p in losses if p.me == "resigned"]
    early = [p for p in resigned if 0 < p.game.moves <= 20]
    mated = sum(p.me == "checkmated" for p in losses)
    if len(early) / len(losses) >= 0.3:
        return _Trait(
            len(early) / len(losses) * 1.5,
            "Speedrun Resigner",
            f"{_pct(len(early), len(losses))} of losses resigned before move 20. One bad move and it's over.",
        )
    if len(resigned) / len(losses) <= 0.15 and mated / len(losses) >= 0.3:
        return _Trait(
            0.75,
            "Stubborn Never-Resigner",
            f"Resigned only {_pct(len(resigned), len(losses))} of lost games. Plays on until mate, out of spite.",
        )
    return None


def _abandons(played: list[_Played]) -> _Trait | None:
    count = sum(p.me == "abandoned" for p in played)
    if count < 3:
        return None
    return _Trait(min(1.0, 0.4 + count / 20), "Ghost of the Board", f"Abandoned {count} games. Just walked away from the board.")


def _live(played: list[_Played]) -> list[_Played]:
    return [p for p in played if p.game.time_class != "daily"]


def _tilt(played: list[_Played]) -> _Trait | None:
    live = _live(played)
    after_win = [b.out == "win" for a, b in pairwise(live) if a.out == "win"]
    after_loss = [b.out == "win" for a, b in pairwise(live) if a.out == "loss"]
    if len(after_win) < MIN_SAMPLE or len(after_loss) < MIN_SAMPLE:
        return None
    good, bad = sum(after_win) / len(after_win), sum(after_loss) / len(after_loss)
    if good - bad >= 0.1:
        return _Trait(
            min(1.0, (good - bad) * 3),
            "Tilt Machine",
            f"Win rate drops from {good * 100:.0f}% to {bad * 100:.0f}% right after a loss. Tilted? Never.",
        )
    if bad - good >= 0.1:
        return _Trait(
            min(1.0, (bad - good) * 3),
            "Comeback Kid",
            f"Wins {bad * 100:.0f}% right after a loss, {good * 100:.0f}% after a win. Needs pain to perform.",
        )
    return None


def _revenge(played: list[_Played]) -> _Trait | None:
    live = _live(played)
    pairs = [
        (a, b)
        for a, b in pairwise(live)
        if a.out == "loss" and a.game.end_time and b.game.start_time
    ]
    if len(pairs) < MIN_SAMPLE:
        return None
    quick = sum(timedelta(0) <= b.game.start_time - a.game.end_time <= REVENGE_GAP for a, b in pairs)
    share = quick / len(pairs)
    if share < 0.5:
        return None
    return _Trait(
        share * 0.95,
        "Revenge Queue Addict",
        f"Starts a new game within 2 minutes of {_pct(quick, len(pairs))} of losses. Revenge is a dish served instantly.",
    )


def _longest(played: list[_Played], result: str) -> int:
    best = run = 0
    for p in played:
        run = run + 1 if p.out == result else 0
        best = max(best, run)
    return best


def _streaks(played: list[_Played]) -> _Trait | None:
    live = _live(played)
    lost, won = _longest(live, "loss"), _longest(live, "win")
    if lost >= 6 and lost / 12 >= won / 15:
        return _Trait(min(1.0, lost / 12), "Free-Fall Artist", f"Lost {lost} games in a row at one point. Touch grass.")
    if won >= 8:
        return _Trait(min(1.0, won / 15), "Heater Merchant", f"Won {won} in a row once. Peak arrogance unlocked.")
    return None


def _quick_mate(played: list[_Played]) -> _Trait | None:
    quick = [p.game.moves for p in played if p.me == "checkmated" and 0 < p.game.moves <= 12]
    if not quick:
        return None
    moves = min(quick)
    return _Trait(
        0.4 + (12 - moves) / 20,
        "Speedrun Victim",
        f"Got checkmated in {moves} moves. We've all been there. Some of us more than once.",
    )


def _rating_trend(played: list[_Played]) -> _Trait | None:
    mode = Counter(p.game.time_class for p in played).most_common(1)[0][0]
    ratings = [p.rating for p in played if p.game.time_class == mode and p.rating]
    if len(ratings) < MIN_SAMPLE:
        return None
    change = ratings[-1] - ratings[0]
    name = MODE_NAMES.get(mode, mode).lower()
    if change >= 50:
        return _Trait(min(1.0, change / 200), "Suspiciously Improving", f"+{change} in {name} lately. Suspicious. Very suspicious.")
    if change <= -50:
        return _Trait(min(1.0, -change / 200), "Free-Fall Specialist", f"Down {-change} in {name} lately. Must be the internet connection.")
    return None


def _draws(played: list[_Played]) -> _Trait | None:
    draws = sum(p.out == "draw" for p in played)
    share = draws / len(played)
    if share < 0.15:
        return None
    return _Trait(min(1.0, share * 3), "Draw Merchant", f"Draws {_pct(draws, len(played))} of games. Peace was always an option.")


def _win_rate(played: list[_Played]) -> _Trait | None:
    wins = sum(p.out == "win" for p in played)
    share = wins / len(played)
    if share >= 0.65:
        return _Trait(min(1.0, (share - 0.5) * 3), "Smurf Suspect", f"Wins {_pct(wins, len(played))} of games. Farming the lower-rated, presumably.")
    if share <= 0.38:
        return _Trait(min(1.0, (0.5 - share) * 3), "Generous Rating Donor", f"Wins {_pct(wins, len(played))} of games. Rating points are a renewable resource.")
    return None


def _fillers(played: list[_Played]) -> list[_Trait]:
    """Mild lines used when a player doesn't have enough extreme traits."""
    wins = sum(p.out == "win" for p in played)
    losses = sum(p.out == "loss" for p in played)
    times = [p.game.end_time for p in played if p.game.end_time]
    days = max(1, (max(times) - min(times)).days) if times else 1
    per_day = len(played) / days
    activity = (
        f"{len(played)} games in {days} days. Job? Hobbies? Sleep?"
        if per_day >= 3
        else f"{len(played)} games in {days} days. A casual. Respect."
    )
    return [
        _Trait(0.2, DEFAULT_PERSONA, activity),
        _Trait(0.1, DEFAULT_PERSONA, f"Won {wins}, lost {losses}. Perfectly balanced, as all things should be."),
        _Trait(0.05, DEFAULT_PERSONA, "Plays the board, not the player. Mostly plays the board badly."),
    ]
