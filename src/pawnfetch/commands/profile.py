from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pawnfetch.client import ChessComClient
from pawnfetch.commands._errors import handle_errors

console = Console()


@handle_errors
def show_profile(username: str) -> None:
    with ChessComClient() as client:
        profile = client.get_profile(username)

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("Username", profile.username)
    if profile.name:
        table.add_row("Name", profile.name)
    if profile.title:
        table.add_row("Title", profile.title)
    table.add_row("Status", profile.status)
    if profile.location:
        table.add_row("Location", profile.location)
    if profile.joined:
        table.add_row("Joined", profile.joined.strftime("%d %b %Y"))
    if profile.last_online:
        table.add_row("Last online", profile.last_online.strftime("%d %b %Y, %H:%M UTC"))
    table.add_row("Followers", str(profile.followers))
    if profile.is_streamer:
        table.add_row("Streamer", "Yes")

    console.print(Panel(table, title=f"chess.com/{profile.username}", border_style="green"))