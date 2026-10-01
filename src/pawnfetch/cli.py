from __future__ import annotations

from importlib.metadata import version

import typer

from pawnfetch.commands.compare import show_compare
from pawnfetch.commands.profile import show_profile
from pawnfetch.commands.stats import show_stats

app = typer.Typer(help="Fetch and compare chess.com player data.")


def show_version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pawnfetch {version('pawnfetch')}")
        raise typer.Exit()


@app.callback()
def main(
    show_version: bool = typer.Option(
        False,
        "--version",
        callback=show_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """pawnfetch: look up and compare chess.com players."""


@app.command()
def profile(username: str) -> None:
    """Look up a player's chess.com profile."""
    show_profile(username)


@app.command()
def stats(username: str) -> None:
    """Show a player's ratings and win/loss record."""
    show_stats(username)


@app.command()
def compare(username1: str, username2: str) -> None:
    """Compare two players' profiles and ratings side by side."""
    show_compare(username1, username2)


if __name__ == "__main__":
    app()