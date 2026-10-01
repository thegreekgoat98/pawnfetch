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
        )


@dataclass
class GameTypeStats:
    rating: int | None = None
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @classmethod
    def from_api(cls, data: dict) -> GameTypeStats:
        last = data.get("last", {})
        record = data.get("record", {})
        return cls(
            rating=last.get("rating"),
            wins=record.get("win", 0),
            losses=record.get("loss", 0),
            draws=record.get("draw", 0),
        )


@dataclass
class PlayerStats:
    username: str
    rapid: GameTypeStats | None = None
    blitz: GameTypeStats | None = None
    bullet: GameTypeStats | None = None
    daily: GameTypeStats | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, username: str, data: dict) -> PlayerStats:
        return cls(
            username=username,
            rapid=_parse_game_type(data, "chess_rapid"),
            blitz=_parse_game_type(data, "chess_blitz"),
            bullet=_parse_game_type(data, "chess_bullet"),
            daily=_parse_game_type(data, "chess_daily"),
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