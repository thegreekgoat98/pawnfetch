from __future__ import annotations

from datetime import datetime, timezone


def intcomma(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def date_short(value: datetime | None) -> str:
    return "" if value is None else f"{value:%b %Y}"


def date_long(value: datetime | None) -> str:
    return "" if value is None else f"{value:%d %b %Y}".lstrip("0")


def duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{int(seconds)}s"


def ago(value: datetime | None, now: datetime | None = None) -> str:
    if value is None:
        return "unknown"
    seconds = int(((now or datetime.now(timezone.utc)) - value).total_seconds())
    if seconds < 60:
        return "just now"
    for unit, size in (("year", 31_536_000), ("month", 2_592_000), ("day", 86_400), ("hour", 3_600), ("minute", 60)):
        if seconds >= size:
            count = seconds // size
            return f"{count} {unit}{'s' if count != 1 else ''} ago"
    return "just now"
