"""Quick write: reading one typed line into an item. Plain rules, no AI.

    "chem lab report fri 5pm #life"  ->  "Chem lab report", Friday, 5:00 PM, the Life label

What is read, and taken out of the title:

- a day: today, tonight, tomorrow (tmr, tmrw, tom), a weekday (fri, friday; "next fri" is the one in next week),
  "next week", "in 3 days", "in 2 weeks", 11/21, 11/21/27, nov 21, 21 nov. No day means today. A date that has
  already passed this year means next year.
- a time: 5pm, 5 pm, 5p, 5:30p, 17:00, noon, midnight (the end of the day), 11:59, and "at 5" (which a student
  means as 5 PM; "at 9" as 9 AM).
- #label, matched against the student's labels by name or the start of one (#app finds Appointment).
- @class, matched against the student's own course codes (@chem finds CHEM 1202, if there's one CHEM course).
- how often: "every mon wed", "every day", "weekdays", "weekly", "monthly on the 1st" (repeats.py). With no day
  typed, the item starts the first time that comes round.
- a type word at the very start: "quiz ch 5" is a quiz and "exam 2" an exam (the word stays in the title);
  "event career fair" is an event.

The first day and the first time win; anything it isn't sure about stays in the title. Each thing read comes back as
a chip saying how it was understood, so the page can show it as the student types, and a word can be handed back
("skip") to be kept as plain text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import reader
import repeats

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_WEEKDAY = re.compile(r"(mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?")
_MONTH = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?")
_DAY_NUM = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?,?")
_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?")
_CLOCK = re.compile(r"(\d{1,2})(?::(\d{2}))?(a|am|p|pm)?")
TODAY = {"today": 0, "tod": 0, "tonight": 0, "tomorrow": 1, "tmr": 1, "tmrw": 1, "tom": 1, "tomo": 1}
KIND_WORDS = ("quiz", "exam", "test", "midterm", "final")
LEAD_INS = ("due", "by", "on", "at", "before")   # "essay due fri": the lead-in goes with the day or time it leads to


@dataclass
class Chip:
    what: str      # day | time | label | class | kind | repeat
    text: str      # the words typed ("next tue"); "" for the day when none was typed
    says: str      # how it was understood ("Tuesday, Nov 24")
    end: int = 0   # where those words end in the line, so Backspace right after them can hand them back


@dataclass
class Read:
    title: str
    day: date
    time: time | None = None
    label: str = ""          # a label's id
    course: str = ""         # "CHEM 1202"
    kind: str = "assignment"  # assignment | quiz | exam | event
    repeat: str = ""          # "weekly:0,2", "monthly:1", "daily" (repeats.py); "" for a one-off
    chips: list[Chip] = field(default_factory=list)

    @property
    def due(self) -> datetime:
        """When it is due, the way the store keeps it (no time: the end of the day)."""
        return datetime.combine(self.day, self.time or time(23, 59))


def say_day(d: date, today: date) -> str:
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return f"{DAY_NAMES[d.weekday()]}, {d:%b} {d.day}" + (f", {d.year}" if d.year != today.year else "")


def say_time(t: time) -> str:
    return datetime.combine(date(2000, 1, 1), t).strftime("%I:%M %p").lstrip("0")


def _weekday(word: str) -> int | None:
    m = _WEEKDAY.fullmatch(word)
    return DAYS.index(m.group(1)[:3]) if m else None


def _month(word: str) -> int | None:
    m = _MONTH.fullmatch(word)
    return MONTHS.index(m.group(1)[:3]) + 1 if m else None


def _this_or_next_year(today: date, month: int, day: int, year: str | None = None) -> date | None:
    try:
        if year:
            y = int(year)
            return date(y + 2000 if y < 100 else y, month, day)
        d = date(today.year, month, day)
        return d if d >= today else date(today.year + 1, month, day)   # already past this year: next year
    except ValueError:
        return None


def _clock(word: str, after_at: bool = False) -> time | None:
    """"5pm", "5:30p", "17:00", "11:59"; with after_at, a bare "5" too. None if it isn't a time."""
    if word in ("noon", "midday"):
        return time(12, 0)
    if word == "midnight":
        return time(23, 59)   # "due midnight" is the end of that day
    m = _CLOCK.fullmatch(word)
    if not m or not (m.group(2) or m.group(3) or after_at):
        return None
    hour, minute, half = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "")[:1]
    if minute > 59:
        return None
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "p" else 0)
    elif hour > 23:
        return None
    elif hour <= 12 and not (m.group(2) and len(m.group(1)) == 2 and hour < 10):   # "09:00" and "17:00" are as written
        if (hour, minute) == (11, 59) or 1 <= hour <= 6:
            hour = hour % 12 + 12       # 11:59 is the deadline; "at 5" is the afternoon
        # 7 to 11 are the morning, 12 is noon
    return time(hour, minute)


def _pick(word: str, choices: dict[str, str]) -> str | None:
    """The one choice (id -> name) that `word` names: its id, its name, or the start of either. None if no one does."""
    word = re.sub(r"[^a-z0-9]", "", word.lower())
    if not word:
        return None
    plain = {k: (re.sub(r"[^a-z0-9]", "", k.lower()), re.sub(r"[^a-z0-9]", "", v.lower())) for k, v in choices.items()}
    exact = [k for k, names in plain.items() if word in names]
    if len(exact) == 1:
        return exact[0]
    starts = [k for k, names in plain.items() if any(n.startswith(word) for n in names)]
    return starts[0] if len(starts) == 1 else None


def _course(word: str, courses: list[str]) -> str | None:
    """"chem" -> "CHEM 1202" if that is the student's only CHEM course; "chem1202" or "1202" name one outright."""
    word = re.sub(r"[^a-z0-9]", "", word.lower())
    if not word:
        return None
    hits = []
    for code in courses:
        letters, _, digits = code.lower().partition(" ")
        if word in (letters + digits, digits) or (word == letters) or (len(word) >= 2 and letters.startswith(word) and not digits.startswith(word)):
            hits.append(code)
    exact = [c for c in hits if word == c.lower().replace(" ", "")]
    if exact:
        return exact[0]
    return hits[0] if len(hits) == 1 else None


def read(text: str, now: datetime, courses: list[str] | None = None, labels: dict[str, str] | None = None,
         skip: list[str] | None = None) -> Read:
    """Read one typed line. `courses` are the student's course codes, `labels` their labels (id -> name), and `skip`
    words they've handed back: those are kept as plain text."""
    today, courses, labels = now.date(), courses or [], labels or {}
    skip = {s.lower() for s in (skip or [])}
    words = [(m.group(0), m.end()) for m in re.finditer(r"\S+", text[:300])]
    low = [w.lower().strip(",.;") if not w.startswith(("#", "@")) else w.lower() for w, _ in words]
    used = [False] * len(words)
    out = Read(title="", day=today)
    chips: dict[str, Chip] = {}

    def take(what: str, start: int, count: int, says: str) -> None:
        typed = " ".join(w for w, _ in words[start:start + count])
        if start and low[start - 1] in LEAD_INS and not used[start - 1] and what in ("day", "time"):
            used[start - 1] = True
        for k in range(start, start + count):
            used[k] = True
        chips[what] = Chip(what, typed, says, words[start + count - 1][1])

    def free(start: int, count: int) -> bool:
        if start + count > len(words) or any(used[start:start + count]):
            return False
        return " ".join(low[start:start + count]) not in skip and not any(w in skip for w in low[start:start + count])

    i = 0
    while i < len(words):
        w = low[i]
        if not free(i, 1):
            i += 1
            continue
        nxt = low[i + 1] if i + 1 < len(words) else ""
        # --- #label and @class
        if w.startswith("#") and "label" not in chips and (got := _pick(w[1:], labels)):
            out.label = got
            take("label", i, 1, labels[got])
        elif w.startswith("@") and "class" not in chips and (code := _course(w[1:], courses)):
            out.course = code
            take("class", i, 1, code)
        # --- how often: "every mon wed", "monthly on the 1st" (repeats.py)
        elif "repeat" not in chips and (hit := repeats.find(low, i)) and free(i, hit[1]):
            out.repeat = hit[0]
            take("repeat", i, hit[1], "")
        # --- a day
        elif "day" not in chips and w in TODAY:
            out.day = today + timedelta(days=TODAY[w])
            take("day", i, 1, say_day(out.day, today))
        elif "day" not in chips and w == "in" and free(i, 3) and nxt.isdigit() and 0 < int(nxt) < 400 \
                and re.fullmatch(r"(days?|weeks?|wks?)", low[i + 2]):
            out.day = today + timedelta(days=int(nxt) * (7 if low[i + 2].startswith("w") else 1))
            take("day", i, 3, say_day(out.day, today))
        elif "day" not in chips and w == "in" and free(i, 3) and nxt in ("a", "one") and low[i + 2] in ("week", "wk"):
            out.day = today + timedelta(days=7)
            take("day", i, 3, say_day(out.day, today))
        elif "day" not in chips and w == "next" and free(i, 2) and nxt in ("week", "wk"):
            out.day = today + timedelta(days=7)
            take("day", i, 2, say_day(out.day, today))
        elif "day" not in chips and w == "next" and free(i, 2) and _weekday(nxt) is not None:
            monday = today - timedelta(days=today.weekday())
            out.day = monday + timedelta(days=7 + _weekday(nxt))
            take("day", i, 2, say_day(out.day, today))
        elif "day" not in chips and w == "this" and free(i, 2) and _weekday(nxt) is not None:
            out.day = today + timedelta(days=(_weekday(nxt) - today.weekday()) % 7)
            take("day", i, 2, say_day(out.day, today))
        elif "day" not in chips and _weekday(w) is not None:
            out.day = today + timedelta(days=(_weekday(w) - today.weekday()) % 7)
            take("day", i, 1, say_day(out.day, today))
        elif "day" not in chips and (m := _SLASH.fullmatch(w)) and \
                (d := _this_or_next_year(today, int(m.group(1)), int(m.group(2)), m.group(3))):
            out.day = d
            take("day", i, 1, say_day(d, today))
        elif "day" not in chips and _month(w) and free(i, 2) and (m := _DAY_NUM.fullmatch(nxt)) and \
                (d := _this_or_next_year(today, _month(w), int(m.group(1)))):
            out.day = d
            take("day", i, 2, say_day(d, today))
        elif "day" not in chips and (m := _DAY_NUM.fullmatch(w)) and free(i, 2) and _month(nxt) and \
                (d := _this_or_next_year(today, _month(nxt), int(m.group(1)))):
            out.day = d
            take("day", i, 2, say_day(d, today))
        # --- a time
        elif "time" not in chips and re.fullmatch(r"\d{1,2}(:\d{2})?", w) and free(i, 2) and nxt in ("am", "pm", "a", "p") \
                and (t := _clock(w + nxt)):
            out.time = t
            take("time", i, 2, say_time(t))
        elif "time" not in chips and w == "at" and free(i, 2) and (t := _clock(nxt, after_at=True)) and \
                not (i + 2 < len(words) and low[i + 2] in ("am", "pm", "a", "p")):
            out.time = t
            used[i] = True
            take("time", i + 1, 1, say_time(t))
        elif "time" not in chips and (t := _clock(w)):
            out.time = t
            take("time", i, 1, say_time(t))
        i += 1

    # a type word at the very start: "quiz ch 5", "exam 2". It stays in the title, which reads better with it, and
    # the app's own rules have the last word ("midterm review session" is not the midterm). "event" is only a marker.
    rest = [k for k in range(len(words)) if not used[k]]
    first = low[0] if rest and rest[0] == 0 and low[0] not in skip else ""
    if first == "event" and len(rest) > 1:
        out.kind = "event"
        take("kind", 0, 1, "Event")
        rest = rest[1:]
    elif first in KIND_WORDS and (lvl := reader.level(" ".join(words[k][0] for k in rest))):
        out.kind = lvl
        chips["kind"] = Chip("kind", words[0][0], lvl.capitalize(), words[0][1])
    elif out.label == "appointment":
        out.kind = "event"   # an appointment is somewhere to be, not work that goes overdue
    title = " ".join(words[k][0] for k in rest).strip(" ,;")
    out.title = title[:1].upper() + title[1:]
    if out.repeat:
        # With no day typed, a repeating item starts the first time it comes round: today, if that's one of its
        # days and its time hasn't gone by. "weekly" and "monthly" alone take their day from the item's own.
        if "day" not in chips:
            start = today + timedelta(days=1) if out.time and datetime.combine(today, out.time) <= now else today
            if repeats.valid(out.repeat):
                out.day = repeats.on_or_after(out.repeat, start)
                chips["day"] = Chip("day", "", say_day(out.day, today), 0)
        out.repeat = repeats.settle(out.repeat, out.day)
        chips["repeat"].says = repeats.say(out.repeat)
    if "day" not in chips:
        chips["day"] = Chip("day", "", "Today", 0)
    out.chips = [chips[k] for k in ("kind", "day", "time", "repeat", "label", "class") if k in chips]
    return out
