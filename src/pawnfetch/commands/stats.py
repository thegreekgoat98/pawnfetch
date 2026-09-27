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
def show_stats(username: str) -> None:
    with ChessComClient() as client:
        stats = client.get_stats(username)

    table = Table(title=f"chess.com/{stats.username} \u2014 stats")
    table.add_column("Format")
    table.add_column("Rating", justify="right")
    table.add_column("W", justify="right")
    table.add_column("L", justify="right")
    table.add_column("D", justify="right")

    any_data = False
    for attr, label in GAME_TYPES:
        game_stats: GameTypeStats | None = getattr(stats, attr)
        if game_stats is None:
            continue
        any_data = True
        table.add_row(
            label,
            str(game_stats.rating) if game_stats.rating is not None else "\u2014",
            str(game_stats.wins),
            str(game_stats.losses),
            str(game_stats.draws),
        )

    if not any_data:
        console.print(f"[yellow]{username} has no recorded stats for rapid/blitz/bullet/daily chess.[/yellow]")
        return

    console.print(table)