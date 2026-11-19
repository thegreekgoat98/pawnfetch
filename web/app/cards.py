"""Share images (1200x630 PNG) for link previews and the Download/Copy image buttons.

Drawn with Pillow in the site's dark theme. Inter (SIL Open Font License, see
fonts/OFL.txt) is a variable font, so one file gives every weight.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw, ImageFont

from pawnfetch.chesscom.models import PlayerProfile
from web.app.roast import Roast

WIDTH, HEIGHT = 1200, 630
FONT_PATH = Path(__file__).parent / "fonts" / "Inter.ttf"
AVATAR_HOSTS = {"images.chesscomfiles.com"}
AVATAR_TIMEOUT = 3.0

BG = "#14121a"
SURFACE = "#1d1a26"
SURFACE_2 = "#262232"
INK = "#f4f1ea"
MUTED = "#a19bb0"
LINE = "#342f45"
ACCENT = "#a78bfa"
ACCENT_INK = "#17102b"
DARK_TEXT = "#1b1530"
MODE_COLORS = {"rapid": "#f5b83d", "blitz": "#ff7a59", "bullet": "#38bdf8", "daily": "#4ade80"}
BULLETS = list(MODE_COLORS.values())


@lru_cache(maxsize=32)
def font(size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_PATH), size)
    f.set_variation_by_axes([min(32, max(14, size)), weight])  # optical size, weight
    return f


def _png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def _canvas(shadow: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((52, 52, WIDTH - 28, HEIGHT - 28), 36, fill=shadow)
    draw.rounded_rectangle((40, 40, WIDTH - 40, HEIGHT - 40), 36, fill=SURFACE, outline=INK, width=4)
    return image, draw


def _fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, weight: int, min_size: int = 20):
    """The largest font (down to min_size) that fits `text` in max_width; truncates if none does."""
    while size > min_size and draw.textlength(text, font=font(size, weight)) > max_width:
        size -= 2
    f = font(size, weight)
    while draw.textlength(text, font=f) > max_width and len(text) > 1:
        text = text[:-2] + "…"
    return text, f


def _wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    rows: list[str] = []
    row = ""
    for word in text.split():
        candidate = f"{row} {word}".strip()
        if row and draw.textlength(candidate, font=f) > max_width:
            rows.append(row)
            row = word
        else:
            row = candidate
    if row:
        rows.append(row)
    return rows


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, color: str, size: int = 22, anchor_right: bool = False) -> int:
    f = font(size, 900)
    width = int(draw.textlength(text, font=f)) + size
    x, y = xy
    if anchor_right:
        x -= width
    draw.rounded_rectangle((x, y, x + width, y + size + 16), 10, fill=fill)
    draw.text((x + size // 2, y + 8 + size // 2), text, font=f, fill=color, anchor="lm")
    return x + width


def _avatar(profile: PlayerProfile, size: int) -> Image.Image:
    """The chess.com avatar as a rounded square; the first letter of the name if unavailable."""
    picture = None
    url = profile.avatar or ""
    if url.startswith("https://") and urlparse(url).hostname in AVATAR_HOSTS:
        try:
            response = httpx.get(url, timeout=AVATAR_TIMEOUT, follow_redirects=False)
            response.raise_for_status()
            picture = Image.open(io.BytesIO(response.content)).convert("RGBA").convert("RGB")
            picture.thumbnail((size * 2, size * 2))
            side = min(picture.size)
            left, top = (picture.width - side) // 2, (picture.height - side) // 2
            picture = picture.crop((left, top, left + side, top + side)).resize((size, size))
        except (httpx.HTTPError, OSError, ValueError):
            picture = None
    if picture is None:
        picture = Image.new("RGB", (size, size), ACCENT)
        letter = (profile.name or profile.username or "?")[0].upper()
        ImageDraw.Draw(picture).text((size / 2, size / 2), letter, font=font(size // 2, 900), fill=ACCENT_INK, anchor="mm")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), size // 5, fill=255)
    framed = Image.new("RGB", (size + 8, size + 8), INK)
    framed_mask = Image.new("L", framed.size, 0)
    ImageDraw.Draw(framed_mask).rounded_rectangle((0, 0, size + 7, size + 7), size // 5 + 4, fill=255)
    framed.paste(picture, (4, 4), mask)
    framed.putalpha(framed_mask)
    return framed


def _brand(draw: ImageDraw.ImageDraw, x: int, y: int, anchor: str = "rs") -> None:
    draw.text((x, y), "pawnfetch.com", font=font(26, 800), fill=ACCENT, anchor=anchor)


def _name(profile: PlayerProfile) -> str:
    return profile.name or profile.username


def roast_card(profile: PlayerProfile, roast: Roast) -> bytes:
    image, draw = _canvas(ACCENT)
    avatar = _avatar(profile, 112)
    image.paste(avatar, (84, 84), avatar)

    x = 230
    _pill(draw, (WIDTH - 88, 92), "ROASTED", ACCENT, ACCENT_INK, 22, anchor_right=True)
    if profile.title:
        x = _pill(draw, (x, 96), profile.title, MODE_COLORS["rapid"], DARK_TEXT, 24) + 12
    name, name_font = _fit(draw, _name(profile), WIDTH - 300 - x, 46, 900, 28)
    draw.text((x, 120), name, font=name_font, fill=INK, anchor="lm")
    draw.text((230, 170), f"@{profile.username}", font=font(26, 500), fill=MUTED, anchor="lm")

    persona, persona_font = _fit(draw, roast.persona, WIDTH - 176, 56, 900, 32)
    draw.text((88, 262), persona, font=persona_font, fill=ACCENT, anchor="ls")

    line_font = font(27, 600)
    y, bottom = 312, 500
    for i, line in enumerate(roast.lines):
        rows = _wrap(draw, line, line_font, WIDTH - 220)
        if y + len(rows) * 38 > bottom:
            break
        draw.rounded_rectangle((90, y + 8, 106, y + 24), 4, fill=BULLETS[i % len(BULLETS)])
        for row in rows:
            draw.text((126, y), row, font=line_font, fill=INK)
            y += 38
        y += 10

    draw.line((88, 516, WIDTH - 88, 516), fill=LINE, width=2)
    facts = f"{roast.games} games · {roast.win_pct:.0f}% won · mostly {roast.main_mode.lower()}"
    draw.text((88, 560), facts, font=font(24, 600), fill=MUTED, anchor="ls")
    _brand(draw, WIDTH - 88, 560)
    return _png(image)


def vs_card(left: PlayerProfile, right: PlayerProfile, rows: list[tuple[str, int | None, int | None, float | None]]) -> bytes:
    """`rows`: (mode key, left rating, right rating, left's Elo odds) for each time control."""
    image, draw = _canvas(MODE_COLORS["bullet"])
    draw.text((WIDTH / 2, 92), "TALE OF THE TAPE", font=font(26, 900), fill=ACCENT, anchor="mm")

    for profile, cx in ((left, 300), (right, WIDTH - 300)):
        avatar = _avatar(profile, 104)
        image.paste(avatar, (cx - 56, 118), avatar)
        name, name_font = _fit(draw, _name(profile), 380, 34, 900, 22)
        draw.text((cx, 268), name, font=name_font, fill=INK, anchor="mm")
        draw.text((cx, 302), f"@{profile.username}", font=font(22, 500), fill=MUTED, anchor="mm")

    draw.ellipse((WIDTH / 2 - 48, 126, WIDTH / 2 + 48, 222), fill=ACCENT, outline=INK, width=4)
    draw.text((WIDTH / 2, 174), "VS", font=font(38, 900), fill=ACCENT_INK, anchor="mm")

    y = 340
    for key, a, b, odds in rows[:3]:
        color = MODE_COLORS.get(key, ACCENT)
        draw.rounded_rectangle((WIDTH / 2 - 90, y, WIDTH / 2 + 90, y + 50), 12, fill=color)
        draw.text((WIDTH / 2, y + 25), key.upper(), font=font(22, 900), fill=DARK_TEXT, anchor="mm")
        for value, cx, wins in ((a, 300, a and b and a > b), (b, WIDTH - 300, a and b and b > a)):
            text = str(value) if value else "—"
            if wins:
                width = draw.textlength(text, font=font(38, 900)) + 28
                draw.rounded_rectangle((cx - width / 2, y + 2, cx + width / 2, y + 48), 12, fill=ACCENT)
            draw.text((cx, y + 25), text, font=font(38, 900), fill=ACCENT_INK if wins else INK, anchor="mm")
        if odds is not None:
            draw.text((WIDTH / 2 - 110, y + 25), f"{odds:.0f}%", font=font(20, 700), fill=MUTED, anchor="rm")
            draw.text((WIDTH / 2 + 110, y + 25), f"{100 - odds:.0f}%", font=font(20, 700), fill=MUTED, anchor="lm")
        y += 60

    draw.line((88, 530, WIDTH - 88, 530), fill=LINE, width=2)
    draw.text((88, 572), "Elo odds per time control", font=font(20, 600), fill=MUTED, anchor="ls")
    _brand(draw, WIDTH - 88, 572)
    return _png(image)


def default_card() -> bytes:
    image, draw = _canvas(ACCENT)
    draw.text((WIDTH / 2, 250), "pawnfetch", font=font(110, 900), fill=INK, anchor="mm")
    draw.text((WIDTH / 2, 350), "chess.com stats, roasts and rivalries", font=font(40, 700), fill=ACCENT, anchor="mm")
    draw.text((WIDTH / 2, 460), "pawnfetch.com", font=font(30, 800), fill=MUTED, anchor="mm")
    return _png(image)
