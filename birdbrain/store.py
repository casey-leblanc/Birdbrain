"""SQLite storage for found items and for text that has already been read."""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from config import DB_PATH

KINDS = ("assignment", "test", "event")
LEVELS = ("", "exam", "quiz")   # "" = decide from the title (report.test_level)
# What a student can say an item is, and how that is stored (kind, level).
WHAT = {"assignment": ("assignment", ""), "quiz": ("test", "quiz"), "exam": ("test", "exam"), "event": ("event", "")}
COURSE_CODE = re.compile(r"\b([A-Z]{2,4})\s?(\d{4})\b")   # "CHEM 1212", "BE 2352"


def course_of(item: "Item") -> str:
    """'CHEM 1212' from the item's course (or, failing that, its title); '' if it names none."""
    for text in (item.course, item.title):
        if m := COURSE_CODE.search(html.unescape(text or "")):
            return f"{m.group(1)} {m.group(2)}"
    return ""


def series_of(title: str) -> str:
    """What a run of similar items has in common: the lead-in before " - " or ":", without its numbers.
    "Biochemical Testing - Indole Test" -> "biochemical testing"; "Exp #19 Quiz: Titration" -> "exp # quiz";
    "Quiz 4" -> "quiz"."""
    lead = re.split(r"\s[-–—]\s|:\s", html.unescape(title), maxsplit=1)[0]
    return " ".join(re.sub(r"\d+", "", lead).lower().split())


def _series_key(item: "Item") -> str | None:
    """Where a student's answer for a whole series is kept; None for an item that names no course (an email's
    lead-in, like "Reminder", is not a series)."""
    course, series = course_of(item), series_of(item.title)
    return f"kindrule:{course}|{series}" if course and series else None


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
    label: str = ""            # for your own items: "life", "work", ... (the label's id; prefs holds its name and colour)
    timed: bool | None = None  # for your own items: whether the time of day is a real one. None: made before 2.0,
                               # when 11:59 PM stood for "no time" (report.has_time)
    planned: date | None = None  # "I'll do it then": the day the student dragged it to, earlier than it's due
    rank: float | None = None    # its place among that day's cards, once the student has put them in order
    snoozed: date | None = None  # hidden until this day (snooze.py); on that day the card says it's back
    repeat: str = ""             # for your own items: "weekly:0,2", "monthly:1", "daily" (repeats.py)


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


_COLUMNS = ("id, source, kind, title, due, course, url, detail, confidence, needs_review, level, done_at, label, timed, "
            "planned, rank, snoozed, repeat")
LABEL_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,23}")   # what a label's id looks like


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
            -- the student's own call on one item, which beats the automatic rules: "archived" or "shown"
            CREATE TABLE IF NOT EXISTS placement (id TEXT PRIMARY KEY, how TEXT);
            """
        )
        have = {r[1] for r in self._db.execute("PRAGMA table_info(items)")}
        with self._db:  # upgrade databases made by earlier versions
            if "level" not in have:
                self._db.execute("ALTER TABLE items ADD COLUMN level TEXT DEFAULT ''")
            if "done_at" not in have:
                self._db.execute("ALTER TABLE items ADD COLUMN done_at TEXT")
            if "label" not in have:   # 2.0: labels for your own items
                self._db.execute("ALTER TABLE items ADD COLUMN label TEXT DEFAULT ''")
            if "timed" not in have:   # 2.0: "due at 11:59 PM" and "no time" are told apart for your own items
                self._db.execute("ALTER TABLE items ADD COLUMN timed INTEGER")
            if "planned" not in have:   # 2.0: where the student dragged a card (planner.py)
                self._db.execute("ALTER TABLE items ADD COLUMN planned TEXT")
                self._db.execute("ALTER TABLE items ADD COLUMN rank REAL")
            if "snoozed" not in have:   # 2.0: hidden until a day (snooze.py)
                self._db.execute("ALTER TABLE items ADD COLUMN snoozed TEXT")
            if "repeat" not in have:   # 2.0: your own items can repeat (repeats.py)
                self._db.execute("ALTER TABLE items ADD COLUMN repeat TEXT DEFAULT ''")

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

    # --- judged text cache (an email already read isn't read again) -------
    def already_judged(self, h: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM judged WHERE hash=?", (h,)).fetchone() is not None

    def mark_judged(self, h: str, item_id: str = "") -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO judged VALUES (?,?)", (h, item_id))

    # --- "What is this?": the student's own answer beats the rules ------------------
    def said(self, item: Item) -> tuple[str, str] | None:
        """(kind, level) if the student has said what this item is, or what its series in that course is."""
        for key in ("said:" + item.id, _series_key(item)):
            if key and (raw := self.get_meta(key)):
                got = json.loads(raw)
                return got["kind"], got["level"]
        return None

    def say_kind(self, item: Item, what: str) -> list[Item]:
        """The student says what this item is ("assignment", "quiz", "exam" or "event"). It holds for the item for
        good, and for the rest of its series in that course, now and as new ones turn up. Returns the other stored
        items it changed."""
        kind, level = WHAT[what]
        answer = json.dumps({"kind": kind, "level": level, "like": item.title})
        self.set_meta("said:" + item.id, answer)
        key, changed = _series_key(item), []
        if key:
            self.set_meta(key, answer)
            with self._lock:
                rows = self._db.execute(f"SELECT {_COLUMNS} FROM items WHERE source != 'manual'").fetchall()
            for other in map(_item, rows):
                if other.id == item.id or _series_key(other) != key or (other.kind, other.level) == (kind, level):
                    continue
                if not self.get_meta("said:" + other.id):   # what they said about that one in particular stands
                    changed.append(other)
        with self._lock, self._db:
            for i in [item] + changed:
                self._db.execute("UPDATE items SET kind=?, level=? WHERE id=?", (kind, level, i.id))
        self._changed()
        return changed

    # --- items ----------------------------------------------------------------
    def upsert(self, item: Item) -> bool:
        """Insert or refresh an item (keeping its completed state, and what the student said it is). Returns True
        if new."""
        if item.source != "manual" and (said := self.said(item)):
            item.kind, item.level = said
        now = datetime.now().isoformat(timespec="seconds")
        due = item.due.isoformat(timespec="minutes") if item.due else None
        with self._lock, self._db:
            exists = self._db.execute("SELECT 1 FROM items WHERE id=?", (item.id,)).fetchone()
            if exists:
                self._db.execute(
                    """UPDATE items SET source=?, kind=?, title=?, due=?, course=?, url=?,
                       detail=?, confidence=?, needs_review=?, level=?, label=?, timed=?, repeat=?, last_seen=? WHERE id=?""",
                    (item.source, item.kind, item.title, due, item.course, item.url,
                     item.detail, item.confidence, int(item.needs_review), item.level, item.label,
                     None if item.timed is None else int(item.timed), item.repeat, now, item.id),
                )
            else:
                self._db.execute(
                    """INSERT INTO items (id, source, kind, title, due, course, url, detail, confidence,
                       needs_review, level, done_at, label, timed, repeat, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?)""",
                    (item.id, item.source, item.kind, item.title, due, item.course, item.url,
                     item.detail, item.confidence, int(item.needs_review), item.level, item.label,
                     None if item.timed is None else int(item.timed), item.repeat, now, now),
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
        """Tick an item off, or untick it. Ticking a repeating item of yours brings the next one; unticking it takes
        that one away again, so there is only ever one of it on the list."""
        was = self.get(item_id)
        stamp = datetime.now().isoformat(timespec="seconds") if done else None
        with self._lock, self._db:
            cur = self._db.execute("UPDATE items SET done_at=? WHERE id=?", (stamp, item_id))
        self._changed()
        if was and was.source == "manual" and was.repeat and bool(was.done_at) != done:
            self._repeat(was, done)
        return cur.rowcount > 0

    def next_of(self, item_id: str) -> Item | None:
        """The card that ticking this repeating one brought, if it's still there."""
        nxt = self.get_meta(f"repeat:next:{item_id}")
        return self.get(nxt) if nxt else None

    def _repeat(self, item: Item, done: bool) -> None:
        import repeats
        if not done:   # unticked: the one it brought goes, unless that has been ticked off or moved on itself
            nxt = self.next_of(item.id)
            if nxt and not nxt.done_at:
                self.delete(nxt.id)
            self.set_meta(f"repeat:next:{item.id}", "")
            return
        day = repeats.next_after(item.repeat, item.due.date(), date.today())
        nxt = Item(id=f"manual:{uuid.uuid4().hex[:12]}", source="manual", kind=item.kind, title=item.title,
                   due=datetime.combine(day, item.due.time()), course=item.course, detail=item.detail, level=item.level,
                   label=item.label, timed=item.timed, repeat=item.repeat)
        self.upsert(nxt)
        self.set_meta(f"repeat:next:{item.id}", nxt.id)

    def snooze(self, item_id: str, until: date | None) -> date | None:
        """Hide a card until a day (None wakes it now). Returns what it was before, so the change can be undone."""
        with self._lock, self._db:
            row = self._db.execute("SELECT snoozed FROM items WHERE id=?", (item_id,)).fetchone()
            self._db.execute("UPDATE items SET snoozed=? WHERE id=?", (until.isoformat() if until else None, item_id))
        self._changed()
        return date.fromisoformat(row[0]) if row and row[0] else None

    # --- where the student put a card: a planned day, a place in its day's order (planner.py) -----
    # A scan never touches these (upsert leaves them alone), so they last across scans and restarts.
    def plan(self, item_id: str, day: date | None) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE items SET planned=? WHERE id=?", (day.isoformat() if day else None, item_id))
        self._changed()

    def set_ranks(self, ranks: dict[str, float | None]) -> None:
        with self._lock, self._db:
            self._db.executemany("UPDATE items SET rank=? WHERE id=?", [(r, i) for i, r in ranks.items()])
        self._changed()

    def set_due(self, item_id: str, due: datetime) -> None:
        """Move one of your own items to another day (a scan decides the due date of everything else)."""
        with self._lock, self._db:
            self._db.execute("UPDATE items SET due=? WHERE id=? AND source='manual'", (due.isoformat(timespec="minutes"), item_id))
        self._changed()

    def open_items(self) -> list[Item]:
        """Everything not ticked off, whenever it is due."""
        with self._lock:
            rows = self._db.execute(f"SELECT {_COLUMNS} FROM items WHERE done_at IS NULL AND due IS NOT NULL ORDER BY due").fetchall()
        return [_item(r) for r in rows]

    def snapshot(self, item_ids: list[str]) -> list[dict]:
        """Where these cards are now (day, plan, order, ticked, archived), so a move can be undone."""
        places = self.placements()
        out = []
        for i in item_ids:
            if item := self.get(i):
                out.append({"id": i, "due": item.due.isoformat(timespec="minutes"), "planned": item.planned.isoformat() if item.planned else None,
                            "rank": item.rank, "done": item.done_at.isoformat(timespec="seconds") if item.done_at else None,
                            "place": places.get(i)})
        return out

    def restore(self, snapshot: list[dict]) -> int:
        """Put cards back where a snapshot says they were. Returns how many."""
        done = 0
        with self._lock, self._db:
            for s in snapshot[:400]:
                row = self._db.execute("SELECT source FROM items WHERE id=?", (str(s.get("id")),)).fetchone()
                if not row:
                    continue
                planned = date.fromisoformat(s["planned"]).isoformat() if s.get("planned") else None
                rank = float(s["rank"]) if s.get("rank") is not None else None
                stamp = datetime.fromisoformat(s["done"]).isoformat(timespec="seconds") if s.get("done") else None
                self._db.execute("UPDATE items SET planned=?, rank=?, done_at=? WHERE id=?", (planned, rank, stamp, s["id"]))
                if row[0] == "manual" and s.get("due"):
                    self._db.execute("UPDATE items SET due=? WHERE id=?",
                                     (datetime.fromisoformat(s["due"]).isoformat(timespec="minutes"), s["id"]))
                if s.get("place") in self.PLACES:
                    self._db.execute("INSERT OR REPLACE INTO placement VALUES (?,?)", (s["id"], s["place"]))
                else:
                    self._db.execute("DELETE FROM placement WHERE id=?", (s["id"],))
                done += 1
        self._changed()
        return done

    def clear_label(self, label_id: str) -> list[str]:
        """A label was deleted: the items that had it keep everything else. Returns their ids, for Undo."""
        with self._lock, self._db:
            ids = [r[0] for r in self._db.execute("SELECT id FROM items WHERE label=?", (label_id,))]
            self._db.execute("UPDATE items SET label='' WHERE label=?", (label_id,))
        if ids:
            self._changed()
        return ids

    def set_label(self, item_ids: list[str], label_id: str) -> None:
        """Put a label (back) on your own items."""
        with self._lock, self._db:
            self._db.executemany("UPDATE items SET label=? WHERE id=? AND source='manual'", [(label_id, i) for i in item_ids])
        self._changed()

    def delete(self, item_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM items WHERE id=?", (item_id,))
            self._db.execute("DELETE FROM placement WHERE id=?", (item_id,))
        self._changed()

    # --- placement: archive one item, or show one the rules would archive ----------
    PLACES = ("archived", "shown")

    def placements(self) -> dict[str, str]:
        with self._lock:
            return dict(self._db.execute("SELECT id, how FROM placement").fetchall())

    def set_placement(self, item_id: str, how: str | None) -> str | None:
        """Archive an item ("archived"), show it despite a keyword or duplicate ("shown"), or leave it to the rules
        (None). Returns what it was before, so the change can be undone."""
        if how not in (*self.PLACES, None):
            raise ValueError(f"unknown placement {how!r}")
        with self._lock, self._db:
            row = self._db.execute("SELECT how FROM placement WHERE id=?", (item_id,)).fetchone()
            if how:
                self._db.execute("INSERT OR REPLACE INTO placement VALUES (?,?)", (item_id, how))
            else:
                self._db.execute("DELETE FROM placement WHERE id=?", (item_id,))
        self._changed()
        return row[0] if row else None

    def remove_missing(self, source_prefix: str, keep_ids: set[str], grace: timedelta | None = None) -> int:
        """Drop items from a structured source that no longer report them
        (e.g. a Moodle assignment that was submitted). With `grace`, only items not seen for at least that
        long go, so one scan that missed them (a page that hadn't finished drawing) can't delete them, and
        they can't come back on the next scan looking new. Returns how many went."""
        cutoff = (datetime.now() - grace).isoformat(timespec="seconds") if grace else None
        gone = 0
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT id, last_seen FROM items WHERE id LIKE ?", (source_prefix + "%",)
            ).fetchall()
            for item_id, last_seen in rows:
                if item_id not in keep_ids and (cutoff is None or (last_seen or "") < cutoff):
                    self._db.execute("DELETE FROM items WHERE id=?", (item_id,))
                    gone += 1
        self._changed()
        return gone

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
                r[8], bool(r[9]), r[10] or "", datetime.fromisoformat(r[11]) if r[11] else None, r[12] or "",
                None if r[13] is None else bool(r[13]), date.fromisoformat(r[14]) if r[14] else None, r[15],
                date.fromisoformat(r[16]) if r[16] else None, r[17] or "")
