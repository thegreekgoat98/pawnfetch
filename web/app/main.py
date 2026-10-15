from __future__ import annotations

import random
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from pawnfetch.chesscom.client import (
    ChessComError,
    ChessComRateLimitError,
    PlayerNotFoundError,
)
from web.app import filters
from web.app.compare import build_sections, tally
from web.app.service import PlayerService

BASE_DIR = Path(__file__).parent
USERNAME_RE = re.compile(r"[A-Za-z0-9_-]{3,25}")
FEATURED_PLAYERS = (
    "hikaru",
    "magnuscarlsen",
    "fabianocaruana",
    "gothamchess",
    "anishgiri",
    "firouzja2003",
    "lachesisq",
    "gmwso",
    "nihalsarin",
    "levonaronian",
    "chesswarrior7197",
    "ericrosen",
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")
for _name in ("intcomma", "date_short", "date_long", "duration", "ago"):
    templates.env.filters[_name] = getattr(filters, _name)


def asset_version(path: str) -> int:
    return int((BASE_DIR / "static" / path).stat().st_mtime)


# Appended to asset URLs so browsers refetch CSS/JS after a rebuild.
templates.env.globals["asset_version"] = asset_version


def render_error(request: Request, status_code: int, heading: str, message: str) -> Response:
    context = {"status_code": status_code, "heading": heading, "message": message}
    return templates.TemplateResponse(request, "error.html", context, status_code=status_code)


def lookup_error(request: Request, exc: ChessComError) -> Response:
    if isinstance(exc, PlayerNotFoundError):
        return render_error(request, 404, "No such player", str(exc))
    if isinstance(exc, ChessComRateLimitError):
        return render_error(
            request, 429, "chess.com is busy", "Too many requests right now. Try again in a minute."
        )
    return render_error(request, 502, "chess.com didn't answer", str(exc))


def featured_card(service: PlayerService) -> dict | None:
    """A random featured player for the home page; None hides the card if chess.com is unavailable."""
    for username in random.sample(FEATURED_PLAYERS, k=2):
        try:
            data = service.get_player(username)
        except PlayerNotFoundError:
            continue  # renamed or closed account: try the next candidate
        except ChessComError:
            return None
        modes = [m for m in (data.stats.rapid, data.stats.blitz, data.stats.bullet) if m]
        total = sum(m.total for m in modes)
        split = None
        if total:
            split = (
                sum(m.wins for m in modes) / total * 100,
                sum(m.draws for m in modes) / total * 100,
                sum(m.losses for m in modes) / total * 100,
            )
        return {"data": data, "split": split}
    return None


def create_app(service: PlayerService | None = None) -> FastAPI:
    player_service = service or PlayerService()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        player_service.close()

    app = FastAPI(title="pawnfetch", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> Response:
        return templates.TemplateResponse(request, "home.html", {"featured": featured_card(player_service)})

    @app.get("/search", response_model=None)
    def search(request: Request, u: str = "") -> Response:
        username = u.strip()
        if not USERNAME_RE.fullmatch(username):
            context = {
                "query": username[:25],
                "error": "Usernames are 3-25 characters: letters, numbers, - or _.",
                "featured": featured_card(player_service),
            }
            return templates.TemplateResponse(request, "home.html", context, status_code=422)
        return RedirectResponse(f"/player/{username.lower()}", status_code=303)

    # Sync handler: FastAPI runs it in a worker thread, so the blocking client is fine.
    @app.get("/player/{username}", response_class=HTMLResponse, response_model=None)
    def player(request: Request, username: str) -> Response:
        if not USERNAME_RE.fullmatch(username):
            raise StarletteHTTPException(status_code=404)
        if username != username.lower():
            return RedirectResponse(f"/player/{username.lower()}", status_code=308)
        try:
            data = player_service.get_player(username)
        except ChessComError as exc:
            return lookup_error(request, exc)
        return templates.TemplateResponse(
            request, "player.html", {"profile": data.profile, "stats": data.stats}
        )

    @app.get("/compare", response_class=HTMLResponse, response_model=None)
    async def compare_form(request: Request, a: str = "", b: str = "") -> Response:
        a, b = a.strip(), b.strip()
        context = {"a": a[:25], "b": b[:25]}
        if not (a and b):
            return templates.TemplateResponse(request, "compare.html", context)
        if not (USERNAME_RE.fullmatch(a) and USERNAME_RE.fullmatch(b)):
            context["error"] = "Usernames are 3-25 characters: letters, numbers, - or _."
        elif a.lower() == b.lower():
            context["error"] = "Pick two different players."
        else:
            return RedirectResponse(f"/compare/{a.lower()}/{b.lower()}", status_code=303)
        return templates.TemplateResponse(request, "compare.html", context, status_code=422)

    @app.get("/compare/{a}/{b}", response_class=HTMLResponse, response_model=None)
    def compare(request: Request, a: str, b: str) -> Response:
        if not (USERNAME_RE.fullmatch(a) and USERNAME_RE.fullmatch(b)):
            raise StarletteHTTPException(status_code=404)
        if a.lower() == b.lower():
            return RedirectResponse(f"/player/{a.lower()}", status_code=303)
        if (a, b) != (a.lower(), b.lower()):
            return RedirectResponse(f"/compare/{a.lower()}/{b.lower()}", status_code=308)
        try:
            left = player_service.get_player(a)
            right = player_service.get_player(b)
        except ChessComError as exc:
            return lookup_error(request, exc)
        sections = build_sections(left, right)
        context = {
            "left": left,
            "right": right,
            "sections": sections,
            "score": tally(sections),
            "a": a,
            "b": b,
        }
        return templates.TemplateResponse(request, "compare.html", context)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return render_error(
                request, 404, "That square doesn't exist.", "We couldn't find the page you were looking for."
            )
        return render_error(request, exc.status_code, "Something went wrong.", "Please try again in a moment.")

    return app


app = create_app()
