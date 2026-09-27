from __future__ import annotations

from rich.console import Console
from rich.table import Table

from pawnfetch.client import ChessComClient
from pawnfetch.commands._errors import handle_errors
from pawnfetch.models import GameTypeStats

console = Console()

GAME_TYPES: list[tuple[str, str]] = [
    ("rapid", "Rapid"),
    ("blitz", "Blitz"),
    ("bullet", "Bullet"),
    ("daily", "Daily"),
]


@handle_errors
def show_compare(username1: str, username2: str) -> None:
    with ChessComClient() as client:
        profile1 = client.get_profile(username1)
        stats1 = client.get_stats(username1)
        profile2 = client.get_profile(username2)
        stats2 = client.get_stats(username2)

    table = Table(title=f"{profile1.username} vs {profile2.username}")
    table.add_column("")
    table.add_column(profile1.username, justify="center")
    table.add_column(profile2.username, justify="center")

    table.add_row("Title", profile1.title or "\u2014", profile2.title or "\u2014")
    table.add_row("Status", profile1.status, profile2.status)
    table.add_row(
        "Location",
        profile1.location or "\u2014",
        profile2.location or "\u2014",
    )
    table.add_row(
        "Joined",
        profile1.joined.strftime("%d %b %Y") if profile1.joined else "\u2014",
        profile2.joined.strftime("%d %b %Y") if profile2.joined else "\u2014",
    )
    table.add_row("Followers", str(profile1.followers), str(profile2.followers))
    table.add_section()

    for attr, label in GAME_TYPES:
        game1: GameTypeStats | None = getattr(stats1, attr)
        game2: GameTypeStats | None = getattr(stats2, attr)
        if game1 is None and game2 is None:
            continue
        table.add_row(
            f"{label} rating",
            _format_rating(game1, game2, is_first=True),
            _format_rating(game1, game2, is_first=False),
        )

    console.print(table)


def _format_rating(
    game1: GameTypeStats | None,
    game2: GameTypeStats | None,
    is_first: bool,
) -> str:
    game = game1 if is_first else game2
    other = game2 if is_first else game1
    if game is None or game.rating is None:
        return "\u2014"

    rating_str = str(game.rating)
    if other is not None and other.rating is not None and game.rating > other.rating:
        return f"[green]{rating_str}[/green]"
    return rating_str