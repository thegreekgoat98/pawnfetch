"""A small SQLite file for things that should survive restarts: stored roasts (so a page and its
share image always show the same text) and the daily count of AI roasts.

Lives on the /data volume next to the puzzles: APP_DB (default data/app.sqlite).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from web.app.roast import Roast

DB_PATH = Path(os.environ.get("APP_DB", "data/app.sqlite"))
SCHEMA = """
CREATE TABLE IF NOT EXISTS roasts (username TEXT PRIMARY KEY, data TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ai_usage (day TEXT PRIMARY KEY, count INTEGER NOT NULL);
"""


class AppStore:
    def __init__(self, path: Path = DB_PATH, clock: Callable[[], float] = time.time):
        self.path = path
        self.clock = clock
        self._lock = threading.Lock()  # writes are tiny; one at a time keeps SQLite simple
        self._ready = False

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if not self._ready:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=5)
            try:
                if not self._ready:
                    db.executescript(SCHEMA)
                    self._ready = True
                with db:  # commit on success, roll back on error
                    yield db
            finally:
                db.close()

    def load_roast(self, username: str) -> Roast | None:
        with self._db() as db:
            row = db.execute("SELECT data, created FROM roasts WHERE username = ?", (username,)).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        for key in ("first", "last"):
            data[key] = datetime.fromisoformat(data[key]) if data[key] else None
        return Roast(**data, created=row[1])

    def save_roast(self, username: str, roast: Roast) -> Roast:
        saved = replace(roast, facts=[], created=self.clock())  # facts are only needed to write it
        data = asdict(saved)
        del data["created"]
        for key in ("first", "last"):
            data[key] = data[key].isoformat() if data[key] else None
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO roasts (username, data, created) VALUES (?, ?, ?)",
                (username, json.dumps(data), saved.created),
            )
        return saved

    def use_ai(self, daily_cap: int) -> bool:
        """Count one AI roast for today (UTC) if under the cap; False once the cap is reached."""
        day = datetime.fromtimestamp(self.clock(), timezone.utc).date().isoformat()
        with self._db() as db:
            row = db.execute("SELECT count FROM ai_usage WHERE day = ?", (day,)).fetchone()
            used = row[0] if row else 0
            if used >= daily_cap:
                return False
            db.execute("INSERT OR REPLACE INTO ai_usage (day, count) VALUES (?, ?)", (day, used + 1))
        return True
