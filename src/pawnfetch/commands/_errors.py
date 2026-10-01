from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TypeVar

import typer
from rich.console import Console

from pawnfetch.client import ChessComError

console = Console(stderr=True)
F = TypeVar("F", bound=Callable[..., None])


def handle_errors(func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ChessComError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
    return wrapper  # type: ignore[return-value]