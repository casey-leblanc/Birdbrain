"""SQLite storage for found items and for text Jev has already judged."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime

from config import DB_PATH

KINDS = ("assignment", "test", "event")
LEVELS = ("", "exam", "quiz")   # "" = decide from the title (report.test_level)


@dataclass
class Item:
    id: str                    # stable key, e.g. "moodle:cm:123", "manual:ab12…"
    source: str                # moodle | outlook-mail | outlook-calendar | manual
    kind: str                  # assignment | test | event
    title: str
    due: datetime | None
    course: str = ""
    url: str = ""
    detail: str = ""
    confidence: float | None = None
    needs_review: bool = False
    level: str = ""            # exam | quiz for tests you added yourself
    done_at: datetime | None = None


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


_COLUMNS = "id, source, kind, title, due, course, url, detail, confidence, needs_review, level, done_at"


class Store:
    def __init__(self, path=DB_PATH):
        self._lock = threading.Lock()
        self.version = 0   # bumped on every item change; the open list page polls it
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY, source TEXT, kind TEXT, title TEXT,
                due TEXT, course TEXT, url TEXT, detail TEXT,
                confidence REAL, needs_review INTEGER,
                first_seen TEXT, last_seen TEXT
            );
            CREATE TABLE IF NOT EXISTS judged (hash TEXT PRIMARY KEY, item_id TEXT);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        have = {r[1] for r in self._db.execute("PRAGMA table_info(items)")}
        with self._db:  # upgrade databases made by earlier versions
            if "level" not in have:
                self._db.execute("ALTER TABLE items ADD COLUMN level TEXT DEFAULT ''")
            if "done_at" not in have:
                self._db.execute("ALTER TABLE items ADD COLUMN done_at TEXT")

    def _changed(self) -> None:
        self.version += 1

    def touch(self) -> None:
        """Mark the list as changed without an item change (e.g. new hidden keywords)."""
        self._changed()

    # --- meta ---------------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    # --- judged text cache (avoids re-asking Jev about the same email) -------
    def already_judged(self, h: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM judged WHERE hash=?", (h,)).fetchone() is not None

    def mark_judged(self, h: str, item_id: str = "") -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO judged VALUES (?,?)", (h, item_id))

    # --- items ----------------------------------------------------------------
    def upsert(self, item: Item) -> bool:
        """Insert or refresh an item (keeping its completed state). Returns True if new."""
        now = datetime.now().isoformat(timespec="seconds")
        due = item.due.isoformat(timespec="minutes") if item.due else None
        with self._lock, self._db:
            exists = self._db.execute("SELECT 1 FROM items WHERE id=?", (item.id,)).fetchone()
            if exists:
                self._db.execute(
                    """UPDATE items SET source=?, kind=?, title=?, due=?, course=?, url=?,
                       detail=?, confidence=?, needs_review=?, level=?, last_seen=? WHERE id=?""",
                    (item.source, item.kind, item.title, due, item.course, item.url,
                     item.detail, item.confidence, int(item.needs_review), item.level, now, item.id),
                )
            else:
                self._db.execute(
                    """INSERT INTO items (id, source, kind, title, due, course, url, detail, confidence,
                       needs_review, level, done_at, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)""",
                    (item.id, item.source, item.kind, item.title, due, item.course, item.url,
                     item.detail, item.confidence, int(item.needs_review), item.level, now, now),
                )
        self._changed()
        return not exists

    def get(self, item_id: str) -> Item | None:
        with self._lock:
            row = self._db.execute(f"SELECT {_COLUMNS} FROM items WHERE id=?", (item_id,)).fetchone()
        return _item(row) if row else None

    def exists(self, item_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone() is not None

    def set_done(self, item_id: str, done: bool) -> bool:
        stamp = datetime.now().isoformat(timespec="seconds") if done else None
        with self._lock, self._db:
            cur = self._db.execute("UPDATE items SET done_at=? WHERE id=?", (stamp, item_id))
        self._changed()
        return cur.rowcount > 0

    def delete(self, item_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM items WHERE id=?", (item_id,))
        self._changed()

    def remove_missing(self, source_prefix: str, keep_ids: set[str]) -> None:
        """Drop items from a structured source that no longer report them
        (e.g. a Moodle assignment that was submitted)."""
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT id FROM items WHERE id LIKE ?", (source_prefix + "%",)
            ).fetchall()
            for (item_id,) in rows:
                if item_id not in keep_ids:
                    self._db.execute("DELETE FROM items WHERE id=?", (item_id,))
        self._changed()

    def items_between(self, start: datetime, end: datetime) -> list[Item]:
        with self._lock:
            rows = self._db.execute(
                f"""SELECT {_COLUMNS} FROM items
                    WHERE due IS NOT NULL AND due >= ? AND due < ? ORDER BY due""",
                (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
            ).fetchall()
        return [_item(r) for r in rows]


def _item(r) -> Item:
    return Item(r[0], r[1], r[2], r[3], datetime.fromisoformat(r[4]) if r[4] else None, r[5], r[6], r[7],
                r[8], bool(r[9]), r[10] or "", datetime.fromisoformat(r[11]) if r[11] else None)
