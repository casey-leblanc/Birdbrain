"""What Birdbrain tells you without being asked, and when. One short line that reads at a glance, never a batch.

    Today: Chem Exp 15 Quiz, Pre-lab and 2 more
    Due tonight: Chem Exp 15 Quiz, Pre-lab
    Exam tomorrow at 9:30 AM: Math Exam 2
    New: Chem Lab 8 report (Thu)

- A morning list (07:30 unless changed): what's overdue and what's due today. Nothing due, nothing said.
- An evening check (19:00): what's due before tomorrow mid-morning, so a 7 AM deadline isn't a surprise.
- One before a test: the day before an exam, three hours before a quiz closes.
- New work found by a scan, as one line however many there are.

This module only decides what to say and when; it keeps what it has already said in the store, so each thing is said
once. The app shows it (a notification on the PC, and the same line on the phone when that's linked).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

import planner
import report
from config import Settings
from store import COURSE_CODE, Item, Store, course_of

TONIGHT_ENDS = time(10, 0)             # "tonight" runs until mid-morning: a 7 AM deadline is tonight's work
LATE = timedelta(hours=4)              # a list missed while the PC was off still comes up to this late
EXAM_LEAD = timedelta(hours=24)        # an exam is said the day before
QUIZ_LEAD = timedelta(hours=3)         # a quiz three hours before it closes
LINE = 90                              # about what a notification shows without cutting it off
NAME = 30


@dataclass
class Notice:
    key: str                           # which one this is: "morning", "evening", "test:<id>", "new"
    title: str                         # "Due tonight"
    text: str                          # "Chem Exp 15 Quiz, Pre-lab"
    ids: list[str] = field(default_factory=list)   # the cards it's about; a click lands on the first

    @property
    def line(self) -> str:
        return f"{self.title}: {self.text}"


def hhmm(text: str) -> time | None:
    """"07:30" -> a time; None for "", "off" or anything that isn't one."""
    try:
        return time.fromisoformat(text.strip()) if text and text.strip() else None
    except ValueError:
        return None


def clock(at: datetime) -> str:
    """"9:30 AM", "5 PM"."""
    hour = at.hour % 12 or 12
    return f"{hour}{'' if at.minute == 0 else f':{at.minute:02d}'} {'AM' if at.hour < 12 else 'PM'}"


def short(item: Item, nicknames: dict | None = None) -> str:
    """A name short enough for a notification: "Chem Exp 15 Quiz" for CHEM 1212's "Exp 15 Quiz (closes Friday)".
    The class comes first, by its nickname if it has one, unless the title already says it."""
    title = re.sub(r"\s*\([^)]*\)\s*$", "", item.title).strip() or item.title.strip()
    code = course_of(item)
    title = COURSE_CODE.sub("", title).strip(" -:,") or title            # the code is said once, in front
    if len(title) > NAME:
        title = title[:NAME].rsplit(" ", 1)[0].rstrip(" -:,") + "…"
    if not code:
        return title
    nick = ((nicknames or {}).get(code) or {}).get("nick") or code.split()[0].capitalize()
    return title if nick.lower() in title.lower() else f"{nick} {title}"


def names(items: list[Item], nicknames: dict | None = None, room: int = LINE) -> str:
    """"A, B and 2 more": as many names as fit the line, soonest first."""
    said: list[str] = []
    for n, item in enumerate(items):
        name = short(item, nicknames)
        left = len(items) - n - 1
        tail = f" and {left} more" if left else ""
        if said and len(", ".join([*said, name])) + len(tail) > room:
            return f"{', '.join(said)} and {len(items) - n} more"
        said.append(name)
    return ", ".join(said)


def on_list(store: Store, settings: Settings, now: datetime) -> list[Item]:
    """Every open card on the list right now (nothing ticked, archived or hidden), soonest first."""
    board = report.build(store, settings, now)
    return sorted((i for c in board.columns for g in c.groups for i in g.items), key=lambda i: i.due)


class Notices:
    """`due(now)` returns what should be said at this moment, and remembers it has been."""

    def __init__(self, store: Store, settings: Settings):
        self.store, self.settings = store, settings

    def _said(self, key: str):
        raw = self.store.get_meta("notice:" + key)
        return json.loads(raw) if raw else None

    def _say(self, key: str, value) -> None:
        self.store.set_meta("notice:" + key, json.dumps(value))

    def _nicks(self) -> dict:
        import prefs
        return prefs.load(self.store).get("courses", {})

    # --- the two lists -------------------------------------------------------------------------------------------
    def morning(self, now: datetime) -> Notice | None:
        today = now.date()
        items = on_list(self.store, self.settings, now)
        late = [i for i in items if i.kind == "assignment" and i.due < now and planner.day_of(i, today) <= today
                and i.due.date() < today]
        due = [i for i in items if planner.day_of(i, today) == today and i not in late]
        if not late and not due:
            return None
        nicks = self._nicks()
        if late and due:
            text = f"{names(due, nicks, LINE - 16)}. {len(late)} overdue"
        elif late:
            text = f"{len(late)} overdue: {names(late, nicks, LINE - 12)}"
        else:
            text = names(due, nicks)
        return Notice("morning", "Today", text, [i.id for i in due + late])

    def evening(self, now: datetime) -> Notice | None:
        ends = datetime.combine(now.date() + timedelta(days=1), TONIGHT_ENDS)
        due = [i for i in on_list(self.store, self.settings, now) if now <= i.due <= ends]
        if not due:
            return None
        return Notice("evening", "Due tonight", names(due, self._nicks()), [i.id for i in due])

    def _lists(self, now: datetime) -> list[Notice]:
        out = []
        for which, at, make in (("morning", self.settings.morning_list, self.morning),
                                ("evening", self.settings.evening_list, self.evening)):
            t = hhmm(at)
            if not t:
                continue
            due = datetime.combine(now.date(), t)
            if now < due or self._said(which) == now.date().isoformat():
                continue
            self._say(which, now.date().isoformat())
            if now - due > LATE:           # the PC was off at the time; tomorrow's will do
                continue
            if n := make(now):
                out.append(n)
        return out

    # --- before a test -------------------------------------------------------------------------------------------
    def _tests(self, now: datetime) -> list[Notice]:
        if not self.settings.test_reminders:
            return []
        said = {k: v for k, v in (self._said("tests") or {}).items() if v >= now.isoformat()}   # forget the past
        out = []
        for i in on_list(self.store, self.settings, now):
            if i.kind != "test" or i.due <= now:
                continue
            exam = report.test_level(i) != "quiz"
            if now < i.due - (EXAM_LEAD if exam else QUIZ_LEAD) or said.get(i.id) == i.due.isoformat():
                continue
            said[i.id] = i.due.isoformat()
            name = short(i, self._nicks())
            hours = (i.due - now).total_seconds() / 3600
            day = "today" if i.due.date() == now.date() else "tomorrow"
            if exam:
                out.append(Notice(f"test:{i.id}", f"Exam {day} at {clock(i.due)}", name, [i.id]))
            else:
                left = f"{round(hours)} hours" if hours >= 1.5 else "an hour" if hours >= .75 else f"{max(1, round(hours * 60))} minutes"
                out.append(Notice(f"test:{i.id}", f"Quiz closes in {left} ({clock(i.due)})", name, [i.id]))
        self._say("tests", said)
        return out

    def due(self, now: datetime | None = None) -> list[Notice]:
        """Call every minute or so. What's returned has been marked as said."""
        now = now or datetime.now()
        if not self.settings.notify:
            return []
        return self._lists(now) + self._tests(now)

    # --- after a scan --------------------------------------------------------------------------------------------
    def new_work(self, new: list[Item], now: datetime | None = None) -> Notice | None:
        """One line for what a scan just found, however many there are."""
        now = now or datetime.now()
        new = sorted(new, key=lambda i: i.due)
        if not new or not self.settings.notify:
            return None
        nicks = self._nicks()
        if len(new) == 1:
            return Notice("new", "New", f"{short(new[0], nicks)} ({report._when(new[0], now, 'date')})", [new[0].id])
        return Notice("new", f"{len(new)} new", names(new, nicks), [i.id for i in new])

    def sample(self, now: datetime | None = None) -> Notice:
        """What a notification looks like, for the "Show me one" button: tonight's if there is one, else the morning's,
        else a made-up line that says so."""
        now = now or datetime.now()
        return (self.evening(now) or self.morning(now)
                or Notice("sample", "Due tonight", "this is what a notification looks like"))
