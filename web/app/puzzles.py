"""Chess puzzles from the Lichess open database, stored in a local SQLite file.

The data is Lichess's puzzle export (https://database.lichess.org/#puzzles), released under
CC0. It isn't in Git or the Docker image; build it on the server with:

    python -m web.app.puzzles import

which downloads the export, keeps a filtered set of well-rated puzzles and writes them to
PUZZLES_DB (default data/puzzles.sqlite). Rows are numbered 1..N in rating order, so a random
puzzle of a given level is one indexed lookup instead of a scan of the table.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import random
import re
import sqlite3
import sys
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

LICHESS_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
DB_PATH = Path(os.environ.get("PUZZLES_DB", "data/puzzles.sqlite"))
ID_RE = re.compile(r"[A-Za-z0-9]{3,10}")

# Import filter: popular, often-played puzzles with a settled rating.
MIN_POPULARITY = 95  # Lichess scale: -100 (disliked) to 100 (liked)
MIN_PLAYS = 1000
MAX_RATING_DEVIATION = 80
PER_LEVEL = 50_000

SCHEMA = """
CREATE TABLE puzzles (
    num INTEGER PRIMARY KEY,  -- 1..N in rating order
    id TEXT NOT NULL UNIQUE,  -- Lichess puzzle id, used in our URLs
    fen TEXT NOT NULL,        -- position before the opponent's first move
    moves TEXT NOT NULL,      -- UCI moves, space separated; the first is the opponent's
    rating INTEGER NOT NULL,
    themes TEXT NOT NULL,
    game_url TEXT NOT NULL
);
CREATE INDEX puzzles_rating ON puzzles (rating);
"""


@dataclass(frozen=True)
class Level:
    slug: str
    label: str
    low: int
    high: int  # exclusive


LEVELS = (
    Level("easy", "Easy", 0, 1400),
    Level("medium", "Medium", 1400, 1900),
    Level("hard", "Hard", 1900, 10_000),
)
LEVELS_BY_SLUG = {level.slug: level for level in LEVELS}
DEFAULT_LEVEL = LEVELS_BY_SLUG["medium"]

# Themes worth showing as tags; length and source tags like "short" or "master" are skipped.
HIDDEN_THEMES = {"short", "long", "veryLong", "oneMove", "master", "masterVsMaster", "superGM"}


def level_for(rating: int) -> Level:
    return next(level for level in LEVELS if level.low <= rating < level.high)


def theme_label(theme: str) -> str:
    """"mateIn2" -> "Mate in 2", "backRankMate" -> "Back rank mate"."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z0-9])", " ", theme).lower()
    return words[:1].upper() + words[1:]


@dataclass(frozen=True)
class Puzzle:
    id: str
    fen: str
    moves: tuple[str, ...]
    rating: int
    themes: tuple[str, ...]
    game_url: str

    @property
    def solver(self) -> str:
        """The visitor's side: the opposite of whoever moves first in the FEN."""
        parts = self.fen.split()
        return "b" if len(parts) > 1 and parts[1] == "w" else "w"

    @property
    def level(self) -> Level:
        return level_for(self.rating)

    @property
    def tags(self) -> list[str]:
        return [theme_label(t) for t in self.themes if t not in HIDDEN_THEMES][:4]

    @classmethod
    def from_row(cls, row: tuple) -> Puzzle:
        id_, fen, moves, rating, themes, game_url = row
        return cls(id_, fen, tuple(moves.split()), rating, tuple(themes.split()), game_url)


class PuzzlesUnavailableError(Exception):
    """The puzzle database hasn't been built (or can't be read)."""


class PuzzleBank:
    """Read-only access to the puzzle database. Each call opens its own short-lived connection."""

    def __init__(self, path: Path = DB_PATH):
        self.path = path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self.path.is_file():
            raise PuzzlesUnavailableError(f"No puzzle database at {self.path}.")
        try:
            connection = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise PuzzlesUnavailableError(str(exc)) from exc
        with closing(connection):
            try:
                yield connection
            except sqlite3.Error as exc:
                raise PuzzlesUnavailableError(str(exc)) from exc

    def get(self, puzzle_id: str) -> Puzzle | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, fen, moves, rating, themes, game_url FROM puzzles WHERE id = ?",
                (puzzle_id,),
            ).fetchone()
        return Puzzle.from_row(row) if row else None

    def random(self, level: Level) -> Puzzle | None:
        with self._connect() as db:
            low, high = db.execute(
                "SELECT min(num), max(num) FROM puzzles WHERE rating >= ? AND rating < ?",
                (level.low, level.high),
            ).fetchone()
            if low is None:
                return None
            row = db.execute(
                "SELECT id, fen, moves, rating, themes, game_url FROM puzzles WHERE num = ?",
                (random.randint(low, high),),
            ).fetchone()
        return Puzzle.from_row(row) if row else None


# Import


def read_rows(text: Iterable[str]) -> Iterator[tuple]:
    """Rows of the Lichess CSV that pass the quality filter, as (id, fen, moves, rating, themes, url)."""
    reader = csv.reader(text)
    header = next(reader, None)
    if header is None or header[:9] != [
        "PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation",
        "Popularity", "NbPlays", "Themes", "GameUrl",
    ]:
        raise ValueError(f"Unexpected puzzle CSV header: {header}")
    for row in reader:
        try:
            id_, fen, moves, rating, deviation, popularity, plays, themes, url = row[:9]
            rating, deviation = int(rating), int(deviation)
            popularity, plays = int(popularity), int(plays)
        except ValueError:
            continue
        if (
            popularity >= MIN_POPULARITY
            and plays >= MIN_PLAYS
            and deviation <= MAX_RATING_DEVIATION
            and ID_RE.fullmatch(id_)
            and len(moves.split()) >= 2
            and url.startswith("https://lichess.org/")
        ):
            yield id_, fen, moves, rating, themes, url


def build(rows: Iterable[tuple], dest: Path, per_level: int = PER_LEVEL) -> dict[str, int]:
    """Write up to `per_level` puzzles per level to a new database at `dest`.

    Built in a temporary file and moved into place at the end, so the running site keeps
    serving the old database until the new one is complete.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.unlink(missing_ok=True)
    counts = dict.fromkeys(LEVELS_BY_SLUG, 0)
    with closing(sqlite3.connect(tmp)) as db:
        db.executescript(
            "CREATE TABLE staging (id TEXT, fen TEXT, moves TEXT, rating INTEGER, themes TEXT, game_url TEXT);"
        )
        for row in rows:
            slug = level_for(row[3]).slug
            if counts[slug] < per_level:
                counts[slug] += 1
                db.execute("INSERT INTO staging VALUES (?, ?, ?, ?, ?, ?)", row)
            if all(count >= per_level for count in counts.values()):
                break
        db.executescript(
            SCHEMA
            + """
            INSERT INTO puzzles (id, fen, moves, rating, themes, game_url)
                SELECT id, fen, moves, rating, themes, game_url FROM staging ORDER BY rating, id;
            DROP TABLE staging;
            """
        )
        db.commit()
        db.execute("VACUUM")
    os.replace(tmp, dest)
    return counts


@contextmanager
def open_export(source: str) -> Iterator[io.TextIOBase]:
    """The Lichess export as decoded CSV text, from a URL or a local .csv/.csv.zst file."""
    import zstandard  # only needed for importing, not for serving puzzles

    if source.startswith("https://"):
        import httpx

        with httpx.stream("GET", source, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            stream = _ResponseReader(response.iter_bytes())
            with zstandard.ZstdDecompressor().stream_reader(stream) as raw:
                yield io.TextIOWrapper(raw, encoding="utf-8", newline="")
        return
    with open(source, "rb") as fh:
        if source.endswith(".zst"):
            with zstandard.ZstdDecompressor().stream_reader(fh) as raw:
                yield io.TextIOWrapper(raw, encoding="utf-8", newline="")
        else:
            yield io.TextIOWrapper(fh, encoding="utf-8", newline="")


class _ResponseReader(io.RawIOBase):
    """Adapts an iterator of byte chunks to a file object that zstandard can read from."""

    def __init__(self, chunks: Iterator[bytes]):
        self._chunks = chunks
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, target: bytearray | memoryview) -> int:
        while not self._buffer:
            self._buffer = next(self._chunks, b"")
            if not self._buffer:
                return 0
        size = min(len(target), len(self._buffer))
        target[:size] = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m web.app.puzzles")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="Build the puzzle database from the Lichess export.")
    importer.add_argument("--source", default=LICHESS_URL, help="URL or local .csv/.csv.zst file")
    importer.add_argument("--db", type=Path, default=DB_PATH, help=f"output file (default {DB_PATH})")
    importer.add_argument("--per-level", type=int, default=PER_LEVEL)
    args = parser.parse_args(argv)

    print(f"Reading {args.source} ...", flush=True)
    with open_export(args.source) as text:
        counts = build(read_rows(text), args.db, args.per_level)
    total = sum(counts.values())
    size = args.db.stat().st_size / 2**20
    print(f"Wrote {total:,} puzzles to {args.db} ({size:.1f} MB): " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
