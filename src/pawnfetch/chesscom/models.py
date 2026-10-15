from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PlayerProfile:
    username: str
    player_id: int
    url: str
    status: str
    title: str | None = None
    name: str | None = None
    avatar: str | None = None
    location: str | None = None
    country_url: str | None = None
    joined: datetime | None = None
    last_online: datetime | None = None
    followers: int = 0
    is_streamer: bool = False
    league: str | None = None

    @property
    def country_code(self) -> str | None:
        if not self.country_url:
            return None
        return self.country_url.rstrip("/").rsplit("/", 1)[-1].upper() or None

    @classmethod
    def from_api(cls, data: dict) -> PlayerProfile:
        return cls(
            username=data["username"],
            player_id=data["player_id"],
            url=data.get("url", ""),
            status=data.get("status", "unknown"),
            title=data.get("title"),
            name=data.get("name"),
            avatar=data.get("avatar"),
            location=data.get("location"),
            country_url=data.get("country"),
            joined=_to_datetime(data.get("joined")),
            last_online=_to_datetime(data.get("last_online")),
            followers=data.get("followers", 0),
            is_streamer=data.get("is_streamer", False),
            league=data.get("league"),
        )


@dataclass
class GameTypeStats:
    rating: int | None = None
    wins: int = 0
    losses: int = 0
    draws: int = 0
    best_rating: int | None = None
    best_date: datetime | None = None
    best_game_url: str | None = None
    time_per_move: int | None = None
    timeout_percent: float | None = None

    @property
    def total(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def win_pct(self) -> float:
        return self._pct(self.wins)

    @property
    def draw_pct(self) -> float:
        return self._pct(self.draws)

    @property
    def loss_pct(self) -> float:
        return self._pct(self.losses)

    def _pct(self, count: int) -> float:
        return count / self.total * 100 if self.total else 0.0

    @classmethod
    def from_api(cls, data: dict) -> GameTypeStats:
        last = data.get("last", {})
        best = data.get("best", {})
        record = data.get("record", {})
        return cls(
            rating=last.get("rating"),
            wins=record.get("win", 0),
            losses=record.get("loss", 0),
            draws=record.get("draw", 0),
            best_rating=best.get("rating"),
            best_date=_to_datetime(best.get("date")),
            best_game_url=best.get("game"),
            time_per_move=record.get("time_per_move"),
            timeout_percent=record.get("timeout_percent"),
        )


@dataclass
class PuzzleRush:
    score: int
    attempts: int


@dataclass
class PlayerStats:
    username: str
    rapid: GameTypeStats | None = None
    blitz: GameTypeStats | None = None
    bullet: GameTypeStats | None = None
    daily: GameTypeStats | None = None
    fide: int | None = None
    tactics_highest: int | None = None
    puzzle_rush: PuzzleRush | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, username: str, data: dict) -> PlayerStats:
        rush = data.get("puzzle_rush", {}).get("best")
        return cls(
            username=username,
            rapid=_parse_game_type(data, "chess_rapid"),
            blitz=_parse_game_type(data, "chess_blitz"),
            bullet=_parse_game_type(data, "chess_bullet"),
            daily=_parse_game_type(data, "chess_daily"),
            fide=data.get("fide") or None,  # chess.com sends 0 for "no FIDE rating"
            tactics_highest=data.get("tactics", {}).get("highest", {}).get("rating"),
            puzzle_rush=PuzzleRush(rush["score"], rush["total_attempts"]) if rush else None,
            raw=data,
        )


def _parse_game_type(data: dict, key: str) -> GameTypeStats | None:
    if key not in data:
        return None
    return GameTypeStats.from_api(data[key])


def _to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)