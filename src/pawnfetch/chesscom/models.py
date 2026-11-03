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
        return _country_code(self.country_url)

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


@dataclass
class LeaderboardEntry:
    rank: int
    username: str
    score: int
    url: str = ""
    title: str | None = None
    name: str | None = None
    avatar: str | None = None
    country_url: str | None = None
    wins: int = 0
    losses: int = 0
    draws: int = 0
    rank_change: int = 0  # positive: moved up the board since chess.com's previous update
    score_change: int = 0

    @property
    def country_code(self) -> str | None:
        return _country_code(self.country_url)

    @property
    def total(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def win_pct(self) -> float:
        return self.wins / self.total * 100 if self.total else 0.0

    @classmethod
    def from_api(cls, data: dict) -> LeaderboardEntry:
        return cls(
            rank=data["rank"],
            username=data["username"],
            score=data["score"],
            url=data.get("url", ""),
            title=data.get("title"),
            name=data.get("name"),
            avatar=data.get("avatar"),
            country_url=data.get("country"),
            wins=data.get("win_count", 0),
            losses=data.get("loss_count", 0),
            draws=data.get("draw_count", 0),
            rank_change=_trend(data.get("trend_rank")),
            score_change=_trend(data.get("trend_score")),
        )


@dataclass
class Leaderboards:
    """Top-50 lists keyed by chess.com's category names, e.g. "live_blitz" or "rush"."""

    boards: dict[str, list[LeaderboardEntry]]

    def get(self, key: str) -> list[LeaderboardEntry]:
        return self.boards.get(key, [])

    @classmethod
    def from_api(cls, data: dict) -> Leaderboards:
        return cls(
            boards={
                key: [LeaderboardEntry.from_api(row) for row in rows]
                for key, rows in data.items()
                if isinstance(rows, list)
            }
        )


@dataclass
class StreamPlatform:
    kind: str  # "twitch", "youtube", ...
    stream_url: str | None = None
    channel_url: str | None = None
    is_live: bool = False
    is_main: bool = False

    @classmethod
    def from_api(cls, data: dict) -> StreamPlatform:
        return cls(
            kind=str(data.get("type") or "other"),
            stream_url=data.get("stream_url"),
            channel_url=data.get("channel_url"),
            is_live=bool(data.get("is_live")),
            is_main=bool(data.get("is_main_live_platform")),
        )


@dataclass
class Streamer:
    username: str
    url: str = ""
    avatar: str | None = None
    is_live: bool = False
    is_community: bool = False
    platforms: list[StreamPlatform] = field(default_factory=list)

    @property
    def live_platform(self) -> StreamPlatform | None:
        """The platform to send viewers to: the one chess.com marks as main, else any live one."""
        live = [p for p in self.platforms if p.is_live]
        return next((p for p in live if p.is_main), live[0] if live else None)

    @classmethod
    def from_api(cls, data: dict) -> Streamer:
        return cls(
            username=data["username"],
            url=data.get("url", ""),
            avatar=data.get("avatar"),
            is_live=bool(data.get("is_live")),
            is_community=bool(data.get("is_community_streamer")),
            platforms=[StreamPlatform.from_api(p) for p in data.get("platforms") or []],
        )


@dataclass
class GamePlayer:
    username: str
    rating: int | None = None
    result: str = ""  # chess.com result code: "win", "checkmated", "agreed", ...

    @classmethod
    def from_api(cls, data: dict) -> GamePlayer:
        return cls(username=data["username"], rating=data.get("rating"), result=data.get("result", ""))


@dataclass
class Game:
    """One finished game from a player's monthly archive. The PGN is not kept."""

    url: str
    white: GamePlayer
    black: GamePlayer
    end_time: datetime | None = None
    time_class: str = ""  # "bullet", "blitz", "rapid", "daily"
    rules: str = "chess"  # "chess" for standard games; "chess960" etc. for variants
    rated: bool = False
    eco_url: str | None = None  # names the opening, e.g. .../openings/Caro-Kann-Defense

    @classmethod
    def from_api(cls, data: dict) -> Game:
        return cls(
            url=data.get("url", ""),
            white=GamePlayer.from_api(data["white"]),
            black=GamePlayer.from_api(data["black"]),
            end_time=_to_datetime(data.get("end_time")),
            time_class=data.get("time_class", ""),
            rules=data.get("rules", "chess"),
            rated=bool(data.get("rated")),
            eco_url=data.get("eco"),
        )


def _trend(trend: dict | None) -> int:
    if not trend:
        return 0
    return int(trend.get("direction", 0)) * int(trend.get("delta", 0))


def _country_code(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").rsplit("/", 1)[-1].upper() or None


def _to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)