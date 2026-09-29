"""Builds the list page. The markup is shared by both layouts; the stylesheet decides:
glass.py for the default Glass layout, CSS below for the Focus layout.

  Now        overdue work, today, tomorrow
  This week  the following five days, one group per day
  Later      exams, quizzes, events and assignments further out

Focus is one calm page: the day as the headline, then the three bands as columns set straight on the
canvas with wide gutters, structure from space and a few light headings rather than boxes or rules.
Exams: accent colour and bold. Quizzes: one step lower, semi-bold with an italic "quiz" label.
Controls are words, not icons. Each layout has its own themes, plus a Custom one (custom.py).

Birdbrain serves this page itself (server.py): ticking an item off moves it to
the Completed bin, "Add item" saves your own items (and "Edit" changes them),
and Settings can start an inbox scan back to a date. Theme, mode, course
colours/nicknames and open bins are saved by Birdbrain (prefs.py) and applied
while the page is built. A read-only copy is also written to today.html.
"""
from __future__ import annotations

import html
import json
import re
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import custom
import filters
import glass
import prefs as prefs_mod
import theme
from config import REPORT_PATH, Settings
from jev import EXAM_RE, QUIZ_RE
from store import Item, Store

SOURCE = {"moodle": "Moodle", "outlook-mail": "Email", "outlook-calendar": "Outlook calendar",
          "gradescope": "Gradescope", "mcgraw": "McGraw Hill Connect", "manual": "Added by you"}
NOT_COURSES = ("Email", "Calendar", "Personal")
e = html.escape



@dataclass
class Group:
    label: str
    items: list[Item]
    when: str = "time"      # "time" or "date" for the item's time line
    urgent: bool = False
    due: str = ""           # "overdue" / "today" / "tomorrow": lets a look colour the heading


@dataclass
class Column:
    title: str
    groups: list[Group]
    empty: str
    kinds: bool = True      # "exam"/"quiz" labels (Later's group labels already say it)

    @property
    def count(self) -> int:
        return sum(len(g.items) for g in self.groups)


@dataclass
class Board:
    columns: list[Column]
    archived: list[filters.Hidden]
    overdue: int
    due_today: int
    tomorrow: int
    exams: list[Item] = field(default_factory=list)      # upcoming, soonest first
    quizzes: list[Item] = field(default_factory=list)
    completed: list[Item] = field(default_factory=list)  # most recently ticked first
    courses: list[str] = field(default_factory=list)     # course codes on the page


def window(store: Store, settings: Settings, now: datetime) -> list[Item]:
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return store.items_between(today - timedelta(days=settings.overdue_days),
                               today + timedelta(days=settings.lookahead_days + 1))


def test_level(i: Item) -> str | None:
    """'exam' for exams/tests/midterms/finals, 'quiz' for quizzes, None otherwise.
    Items you added and Moodle quiz activities say which they are; otherwise the
    title decides, and an assessment that names neither is treated as an exam so
    none gets missed."""
    if i.kind != "test":
        return None
    if i.level in ("exam", "quiz"):
        return i.level
    t = display_title(i)
    if EXAM_RE.search(t):
        return "exam"
    return "quiz" if QUIZ_RE.search(t) else "exam"


def build(store: Store, settings: Settings, now: datetime | None = None) -> Board:
    now = now or datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day = lambda n: today + timedelta(days=n)
    everything = window(store, settings, now)
    completed = sorted((i for i in everything if i.done_at), key=lambda i: i.done_at, reverse=True)
    # Duplicates are judged against every Moodle item, ticked off or not.
    items, archived = filters.split([i for i in everything if not i.done_at], settings.hidden_keywords,
                                    pool=everything, placement=store.placements())

    overdue = [i for i in items if i.kind == "assignment" and i.due < now]
    todays = [i for i in items if day(0) <= i.due < day(1) and not (i.kind == "assignment" and i.due < now)]
    tomorrow = [i for i in items if day(1) <= i.due < day(2)]
    week = [Group(f"{day(n):%A}, {day(n):%b} {day(n).day}", [i for i in items if day(n) <= i.due < day(n + 1)])
            for n in range(2, 7)]
    later = [i for i in items if i.due >= day(7)]
    upcoming = [i for i in items if i.due >= now]
    codes = {course_code(i) for i in everything}
    return Board(
        columns=[
            Column("Now", [Group("Overdue", overdue, "date", urgent=True, due="overdue"),
                           Group("Today", todays, due="today"), Group("Tomorrow", tomorrow, due="tomorrow")],
                   "Nothing due right now."),
            Column("This week", week, "Nothing else this week."),
            # One list in date order; exam and quiz chips mark the tests.
            Column("Later", [Group(f"From {day(7):%A}, {day(7):%b} {day(7).day}", sorted(later, key=lambda i: i.due), "date")],
                   "Nothing further out yet."),
        ],
        archived=archived,
        overdue=len(overdue),
        due_today=len(todays),
        tomorrow=len(tomorrow),
        exams=[i for i in upcoming if test_level(i) == "exam"],
        quizzes=[i for i in upcoming if test_level(i) == "quiz"],
        completed=completed,
        courses=sorted(c for c in codes if c not in NOT_COURSES),
    )


# --- item text ----------------------------------------------------------------
def course_code(i: Item) -> str:
    """'2026 Fall CHEM 1212 for A. Instructor' -> 'CHEM 1212'."""
    texts = (i.course,) if i.source in ("moodle", "manual") else (i.course, i.title, i.detail)
    for t in texts:
        if m := filters.COURSE_CODE.search(html.unescape(t or "")):
            return f"{m.group(1)} {m.group(2)}"
    if i.source == "manual":
        return i.course[:14] or "Personal"
    if i.source == "moodle":
        return (i.course or "Moodle")[:14]
    return "Email" if i.source == "outlook-mail" else "Calendar"


def display_title(i: Item) -> str:
    """Drop what the course code already says: 'Moodle4 - [2026 Fall CE 2450 ...] ' or
    '2026 Fall BE 2352 for B. Instructor: ' in front of email subjects."""
    t = html.unescape(i.title)
    if i.source == "manual":
        return t
    t = re.sub(r"^\s*moodle\d*\s*-\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*\[[^\]]*\]\s*", "", t)
    t = re.sub(r"^\s*\d{4}\s+(fall|spring|summer|winter)\s+[A-Z]{2,4}\s?\d{4}\b[^:]*:\s*", "", t, flags=re.I)
    if i.source == "outlook-calendar" and re.match(r"^\d{1,2}:\d{2}\s*[AP]M\b", t, re.I):
        return "Untitled event"   # Outlook gave no subject, only the time range
    return t.strip() or html.unescape(i.title)


def has_time(i: Item) -> bool:
    if "time not stated" in i.detail or i.id.startswith("moodle:page:"):
        return False
    return i.source == "moodle" or (i.due.hour, i.due.minute) not in ((23, 59), (0, 0))


def _time(d: datetime) -> str:
    return d.strftime("%I:%M %p").lstrip("0")


def _when(i: Item, now: datetime, style: str) -> str:
    """The time line under an item: a time for today/tomorrow/this week, a date further out."""
    if style == "date":
        return f"{i.due:%b} {i.due.day}" + (f", {_time(i.due)}" if has_time(i) and i.due >= now else "")
    return _time(i.due) if has_time(i) else ""   # the group heading already names the day


def _when_long(i: Item, now: datetime) -> str:
    days = (i.due.date() - now.date()).days
    rel = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    return f"{i.due:%a, %b} {i.due.day}" + (f", {_time(i.due)}" if has_time(i) else "") + f", {rel}"


def urgency(i: Item, now: datetime) -> str:
    """How pressing an open item's due date is: overdue, today, tomorrow, soon (2-3 days) or ""."""
    if i.due < now:
        return "overdue" if i.kind == "assignment" else ""   # past events and tests are over, not late
    days = (i.due.date() - now.date()).days
    return "today" if days == 0 else "tomorrow" if days == 1 else "soon" if days <= 3 else ""


def _detail(i: Item) -> str:
    if i.id.startswith("moodle:page:"):
        return "Found in the course page text; no time was given."
    if i.source == "outlook-mail":
        return f"Email from {i.course}: {i.detail}" if i.detail else f"Email from {i.course}"
    if i.source == "outlook-calendar":
        return i.detail
    if i.source == "manual":
        return f"Added by you. {i.detail}" if i.detail else "Added by you."
    return ""


def _code(code: str, courses: dict[str, dict]) -> str:
    """A course code, with your nickname if set, and a dot of your colour for it once you've picked one."""
    mine = courses.get(code, {})
    style = f' style="--cc:{e(mine["color"])}"' if mine.get("color") else ""
    return (f'<span class="code" data-code="{e(code)}"{style} title="{e(code) if mine.get("nick") else ""}">'
            f'{e(mine.get("nick") or code)}</span>')


def _due_words(i: Item, now: datetime) -> str:
    """When an item is due, in full, for screen readers: the page shows it as a day heading plus a time."""
    when = f"{i.due:%A, %B} {i.due.day}" + (f", {_time(i.due)}" if has_time(i) else "")
    if urgency(i, now) == "overdue":
        return f"Overdue, was due {when}"
    if i.due < now:
        return f"Was on {when}"
    return f"{'On' if i.kind == 'event' else 'Due'} {when}"


def _manual_fields(i: Item) -> str:
    """What the Edit form is pre-filled with, for items you added."""
    kind = (i.level or "exam") if i.kind == "test" else i.kind
    no_time = (i.due.hour, i.due.minute) == (23, 59)
    return json.dumps({"title": i.title, "kind": kind, "date": i.due.date().isoformat(),
                       "time": "" if no_time else f"{i.due:%H:%M}", "course": i.course, "notes": i.detail})


def _row(i: Item, when: str, now: datetime, courses: dict, kinds: bool = True,
         reason: str = "", done: bool = False, urgent: bool = False) -> str:
    code, title = course_code(i), display_title(i)
    level = None if (reason or done) else test_level(i)
    tip = ", ".join(x for x in (html.unescape(i.title), i.course, SOURCE.get(i.source, "")) if x)
    name = (f'<a class="t" href="{e(i.url)}" target="_blank" rel="noopener noreferrer" title="{e(tip)}">'
            f'{e(title)}<span class="sr"> (opens in a new tab)</span></a>' if i.url
            else f'<span class="t" title="{e(tip)}">{e(title)}</span>')
    meta = ""
    if level and kinds:
        meta += f'<span class="kind">{level}</span>'
    meta += _code(code, courses)
    meta += f'<time class="w{" late" if urgent else ""}" datetime="{i.due:%Y-%m-%dT%H:%M}">{e(_when(i, now, when))}</time>'
    if i.needs_review and not (reason or done):
        meta += '<span class="unsure" title="This date was read from text; double-check it">date unsure</span>'
    if not (reason or done):   # any item can be put out of the way; it waits in Archived
        meta += (f'<button type="button" class="act arch needs-app" aria-label="Archive {e(title)}">Archive</button>')

    did = f"d{zlib.crc32(i.id.encode()):x}"
    acts = (f'<span class="acts needs-app"><button type="button" class="act edit">Edit</button>'
            f'<button type="button" class="act del">Delete</button></span>' if i.source == "manual" else "")
    if done:
        stamp = f"{i.done_at:%a, %b} {i.done_at.day} at {_time(i.done_at)}"
        tail = f'<p class="detail">Completed {e(stamp)}. {acts}</p>'   # the bin's hint says how to put it back
    elif reason:
        tail = (f'<p class="detail">Hidden: {e(reason)}. <span class="acts needs-app"><button type="button" class="act show" '
                f'aria-label="Show {e(title)} on your list">Show on list</button></span></p>')
    elif detail := _detail(i):
        meta += (f'<button class="act more" type="button" aria-expanded="false" aria-controls="{did}">'
                 f'Details</button>')
        tail = f'<p class="detail" id="{did}" hidden>{e(detail)} {acts}</p>'
    else:
        tail = ""
    classes = "row" + (f" {level}" if level else "") + (" is-done" if done else "") + (
        " past" if not (reason or done) and i.kind != "assignment" and i.due < now else "")
    checked = " checked" if done else ""
    # The tick box's name is the title; its description says what and when, as the row shows it.
    said = ""
    if not (reason or done):
        what = [level.capitalize() if level else "", courses.get(code, {}).get("nick") or code, _due_words(i, now)]
        said = f'<span id="{did}w" hidden>{e(", ".join(x for x in what if x))}</span>'
    desc = f' aria-describedby="{did}w"' if said else ""
    fields = f' data-manual="{e(_manual_fields(i))}"' if i.source == "manual" else ""
    if not (reason or done) and (due := urgency(i, now)):
        fields += f' data-due="{due}"'
    return (f'<li class="{classes}" data-id="{e(i.id)}"{fields}><label class="tickwrap">'
            f'<input class="tick" type="checkbox"{checked} aria-label="{"Not done" if done else "Done"}: {e(title)}"'
            f'{desc}>'
            f'</label><div class="body">{name}<p class="meta">{meta}</p>{said}{tail}</div></li>')


# --- page -----------------------------------------------------------------------
# The lookout's bird, perched: shown when Now is empty. Drawn for Birdbrain; it takes the text colour.
PERCH = ('<svg class="perch" viewBox="0 0 96 60" aria-hidden="true" focusable="false">'
         '<path class="branch" d="M3 52C28 49.5 58 53 93 50"/>'
         '<g class="perched"><path class="legs" d="M44.5 44 43.5 51.5M50.5 43 50.5 51.5"/>'
         '<path class="bird" fill-rule="evenodd" d="M30 40C32 30 40 23 50 21 51 14 56 9 62 9 67 9 70 12 71 16L77 17.5 71 19.5'
         'C71 29 64 39 52 42.5 46 44.5 40 44.5 36 43.5L18 52 15 49.5ZM65.6 14.8a1.6 1.6 0 1 0-3.2 0 1.6 1.6 0 1 0 3.2 0Z"/>'
         '<path class="wing" d="M34 36c6-7 14-9 21-6M37.5 40c5.5-3.5 11.5-4.5 16-3"/></g></svg>')
# A bird in flight, far off: marks "nothing left for today", and it's the bird that flies in to land on the branch.
WING = ('<svg class="wingmark" viewBox="0 0 24 12" aria-hidden="true" focusable="false">'
        '<path d="M1.5 9.5C5 3.5 9 3 12 8c3-5 7-4.5 10.5 1.5"/></svg>')


def _all_clear(b: Board, settings: Settings, now: datetime) -> str:
    """Now has nothing in it: the bird can rest. Says what comes next, so the calm is also useful, unless the
    next exam or quiz line above already names it."""
    ahead = sorted((i for c in b.columns[1:] for g in c.groups for i in g.items if i.due >= now), key=lambda i: i.due)
    shown = {x.id for x in (_next_item("exam", b.exams, now), _next_item("quiz", b.quizzes, now)) if x}
    if ahead:
        nxt = ahead[0]
        more = ("" if nxt.id in shown else
                f'Next up: <b>{e(display_title(nxt))}</b> on {nxt.due:%A}, {nxt.due:%b} {nxt.due.day}.')
    else:
        more = f"Nothing else in the next {settings.lookahead_days} days, either."
    return (f'<div class="clear">{PERCH}<h3 class="clear-head">all clear</h3>'
            f'<p class="clear-sub">Nothing is due today or tomorrow.</p>'
            + (f'<p class="clear-next">{more}</p>' if more else "") + '</div>')


def _first_scan() -> str:
    """Before the first scan has finished, Now says what's happening, so an empty list doesn't read as a result."""
    return (f'<div class="clear first">{WING}<h3 class="clear-head">reading your courses</h3>'
            '<p class="clear-sub">The first scan reads every course page, so it takes a few minutes. '
            "Your deadlines appear here as soon as it's done.</p></div>")


def _day_clear(b: Board, now: datetime) -> str:
    """Nothing overdue or due today, but tomorrow has items: a quiet line where today's items were."""
    finished = any(i.done_at and i.done_at.date() == now.date() and i.due.date() <= now.date() for i in b.completed)
    return f'<p class="dayclear">{WING}{"nothing left for today" if finished else "nothing due today"}</p>'


def _column(c: Column, now: datetime, courses: dict, b: Board | None = None, settings: Settings | None = None,
            scanned: bool = True) -> str:
    slug = re.sub(r"\W+", "-", c.title.lower())
    body = ""
    for g in c.groups:
        if g.items:
            rows = "".join(_row(i, g.when, now, courses, kinds=c.kinds, urgent=g.urgent) for i in g.items)
            due = f' data-due="{g.due}"' if g.due else ""
            label = f'<h3 class="grp{" urgent" if g.urgent else ""}"{due}>{e(g.label)}</h3>' if g.label else ""
            body += f"{label}<ul>{rows}</ul>"
    if c.title == "Now" and b is not None and settings is not None:
        if not c.count:
            body = _all_clear(b, settings, now) if scanned else _first_scan()
        elif not (c.groups[0].items or c.groups[1].items):
            body = _day_clear(b, now) + body
    body = body or f'<p class="empty">{e(c.empty if scanned else "Waiting for the first scan.")}</p>'
    noun = "item" if c.count == 1 else "items"
    return (f'<section class="band" aria-labelledby="h-{slug}"><h2 id="h-{slug}">{e(c.title)}'
            f'<span class="n">{c.count}<span class="sr"> {noun}</span></span></h2>{body}</section>')


def _counts(b: Board) -> str:
    on = lambda n, c: f' class="{c}"' if n else ""
    return (f'<span{on(b.overdue, "o")} data-due="overdue">{b.overdue} overdue</span>'
            f'<span{on(b.due_today, "on")} data-due="today">{b.due_today} today</span>'
            f'<span{on(b.tomorrow, "on")} data-due="tomorrow">{b.tomorrow} tomorrow</span>')


def _next_item(level: str, items: list[Item], now: datetime) -> Item | None:
    """The exam or quiz the next-exam line names: an entry whose date came straight from Moodle/Outlook before one
    read from text. None for a quiz already listed under Now, so it isn't shown twice."""
    if not items:
        return None
    nxt = next((i for i in items if not i.needs_review), items[0])
    if level == "quiz" and nxt.due < now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2):
        return None
    return nxt


def _next(level: str, items: list[Item], settings: Settings, now: datetime, courses: dict, scanned: bool = True) -> str:
    one = "exam" if level == "exam" else "quiz"
    if not items:
        none = f"None in the next {settings.lookahead_days} days." if scanned else "Waiting for the first scan."
        return f'<div class="nx {level}"><h2 class="k">Next {one}</h2><p class="none">{none}</p></div>'
    nxt = _next_item(level, items, now)
    if nxt is None:
        return ""
    when = _when_long(nxt, now) + (", date unsure" if nxt.needs_review else "")
    due = f' data-due="{u}"' if (u := urgency(nxt, now)) else ""
    return (f'<div class="nx {level}"{due}><h2 class="k">Next {one}</h2>'
            f'<p class="t">{e(display_title(nxt))}</p>'
            f'<p class="meta">{_code(course_code(nxt), courses)}<span class="w">{e(when)}</span></p></div>')


def _bin(kind: str, title: str, hint: str, rows: str, count: int, is_open: bool) -> str:
    noun = "item" if count == 1 else "items"
    return (f'<details class="bin {kind}" data-bin="{kind}"{" open" if is_open else ""}><summary>'
            f'<h2 class="bin-title">{title}</h2><span class="n">{count}<span class="sr"> {noun}</span></span>'
            f'<span class="state" aria-hidden="true"></span></summary><p class="hint">{hint}</p>'
            f'<ul class="bin-grid">{rows}</ul></details>')


def _bins(b: Board, settings: Settings, now: datetime, courses: dict, opened: dict) -> str:
    out = ""
    if b.completed:
        rows = "".join(_row(i, "date", now, courses, done=True) for i in b.completed)
        out += _bin("completed", "Completed", "Items you've ticked off. Untick one to put it back.", rows,
                    len(b.completed), opened.get("completed", False))
    if b.archived:
        kws = ", ".join(f"“{e(k)}”" for k in settings.hidden_keywords) or "none yet"
        rows = "".join(_row(h.item, "date", now, courses, reason=h.reason)
                       for h in sorted(b.archived, key=lambda h: h.item.due))
        out += _bin("archived", "Archived", f"Duplicates, entries matching your hidden keywords ({kws}), and anything "
                    "you archived. Show any of them on your list again, or change keywords in Settings, under Keywords.",
                    rows, len(b.archived),
                    opened.get("archived", False))
    return f'<div class="bins">{out}</div>' if out else ""


def render_board(b: Board, settings: Settings, status: str, now: datetime, version: int = 0,
                 prefs: dict | None = None) -> str:
    """Everything inside the page wrapper; the live page swaps this in after a change."""
    prefs = prefs or prefs_mod.DEFAULTS
    courses = prefs["courses"]
    warn = any(w in status.lower() for w in ("sign-in", "failed", "couldn't reach"))
    # An empty list isn't "all clear" until a scan has looked (the first scan is always a full one).
    scanned = not status.lower().startswith(("not scanned", "full moodle scan"))
    return "".join([
        '<header class="top">',
        '<h1>Birdbrain</h1>',
        f'<p class="status{" problem" if warn else ""}">{e(status)}</p>',
        # the counts wait for the first scan: "0 overdue" before anything has been read would be a false all clear
        f'<div class="today"><h2 class="date">{now:%A, %B} {now.day}</h2>'
        + (f'<p class="counts">{_counts(b)}</p>' if scanned else "") + '</div>',
        '<nav class="actions needs-app" aria-label="Actions">',
        '<button id="open-add" class="act strong" type="button" aria-haspopup="dialog" aria-keyshortcuts="N" '
        'title="Add item (N)">Add item</button>',
        '<button id="open-settings" class="act" type="button" aria-haspopup="dialog" aria-keyshortcuts="S" '
        'title="Settings (S)">Settings</button></nav>',
        '</header>',
        '<section class="next" aria-label="Next exam and quiz">',
        _next("exam", b.exams, settings, now, courses, scanned), _next("quiz", b.quizzes, settings, now, courses, scanned),
        "</section>",
        '<main class="bands">', "".join(_column(c, now, courses, b, settings, scanned) for c in b.columns), "</main>",
        _bins(b, settings, now, courses, prefs["bins"]),
        # today-left: overdue plus due today, so the page can tell when you've ticked off the last of them
        f'<span id="board-meta" hidden data-version="{version}" data-today-left="{b.overdue + b.due_today}"></span>',
    ])


def keyword_counts(b: Board, keywords: list[str]) -> list[dict]:
    """How many entries each hidden keyword is keeping off the list."""
    return [{"keyword": k, "count": sum(1 for h in b.archived if filters.keyword_hit(h.item, [k]))} for k in keywords]


def _half(name: str, key: str, mode: str, label: str, body: str, cls: str, style: str = "") -> str:
    word = "Day" if mode == "light" else "Night"
    radio = f'<input type="radio" name="{name}" value="{key}:{mode}" aria-label="{e(label)}, {word.lower()}">'
    return f'<label class="half {cls}" data-slot="{mode}"{style}>{radio}{body.replace("WORD", word)}</label>'


def _photo_half(name: str, key: str, mode: str, label: str, url: str | None) -> str:
    if url:
        return _half(name, key, mode, label, "<span>WORD</span>", "photo", f' style="background-image:url(&quot;{e(url)}&quot;)"')
    return _half(name, key, mode, label, "<span>WORD</span><em>Add a photo</em>", "photo no-photo")


def _tone_half(name: str, key: str, mode: str, label: str, t: dict) -> str:
    """A Focus theme's day or night: its canvas, a heading word, a line of text and the overdue colour."""
    body = (f'<span class="tone-word" style="color:{t["struct"]}">WORD</span>'
            f'<span class="tone-ink" style="background:{t["text"]}"></span><span class="tone-dot" style="background:{t["accent"]}"></span>')
    return _half(name, key, mode, label, body, "tone", f' style="background:{t["bg"]}"')


def _card(key: str, label: str, halves: str) -> str:
    return (f'<div class="theme-opt" data-theme="{key}"><div class="swatch">{halves}</div>'
            f'<span class="theme-name">{e(label)}</span></div>')


def _theme_options(layout: str, photo, p: dict, name: str = "look", with_custom: bool = True) -> str:
    """One card per theme of this layout; its day (light) and night (dark) halves are each a choice. Glass
    themes show their photos, Focus themes their colours. Custom comes last."""
    cards = ""
    if layout == "glass":
        for key, sc in glass.SCHEMES.items():
            cards += _card(key, sc["name"], "".join(
                _photo_half(name, key, m, sc["name"], photo(glass.photo_name(key, m, thumb=True))) for m in ("light", "dark")))
        if with_custom:
            th = custom.thumbs(p, photo)
            cards += _card("custom", "Custom", "".join(_photo_half(name, "custom", m, "Custom", th[m]) for m in ("light", "dark")))
    else:
        for key, th in theme.THEMES.items():
            cards += _card(key, th["name"], "".join(_tone_half(name, key, m, th["name"], th["modes"][m]) for m in ("light", "dark")))
        if with_custom:
            picks = custom.focus_picks(p)
            cards += _card("custom", "Custom", "".join(
                _tone_half(name, "custom", m, "Custom", custom.focus_tokens(picks[m])) for m in ("light", "dark")))
    return cards


def _custom_panel(layout: str, photo, p: dict) -> str:
    """Shown while Custom is the theme: photos and an accent for Glass, four colours per mode for Focus."""
    if layout == "glass":
        th = custom.thumbs(p, photo)
        slots = ""
        for m, word in (("light", "Day"), ("dark", "Night")):
            pic = f' style="background-image:url(&quot;{e(th[m])}&quot;)"' if th[m] else ""
            slots += (f'<div class="slot" data-slot="{m}"><div class="slot-pic{"" if th[m] else " no-photo"}"{pic}><span>{word}</span></div>'
                      f'<label class="btn file-btn">Choose a picture<input type="file" class="sr" '
                      f'accept="image/jpeg,image/png,image/webp" aria-label="Choose a {word.lower()} picture"></label>'
                      f'<button type="button" class="act slot-remove"{"" if th[m] else " hidden"}>Remove</button></div>')
        accent = ((p.get("glass_custom") or {}).get("accent") or custom.GLASS_ACCENT).lower()
        return ('<div class="custom-panel" id="custom-panel" data-kind="glass" hidden><h4 class="sub">Your theme</h4>'
                f'<div class="slots">{slots}</div>'
                '<p class="hint">Any JPEG, PNG or WebP picture. Birdbrain keeps its own copy on this PC, tints the glass to '
                'match it, and darkens the glass as much as your picture needs to keep every word readable.</p>'
                f'<label class="cpick"><input type="color" id="glass-accent" value="{accent}">'
                '<span>Accent <em>the title and exam chips</em></span></label>'
                '<p class="hint" id="custom-msg" aria-live="polite"></p></div>')
    picks, warns = custom.focus_picks(p), custom.focus_warnings(p)
    cols = ""
    for m, word in (("light", "Day"), ("dark", "Night")):
        pickers = "".join(
            f'<label class="cpick"><input type="color" data-mode="{m}" data-role="{r}" value="{picks[m][r].lower()}"><span>{lbl}</span></label>'
            for r, lbl in (("bg", "Background"), ("text", "Text"), ("struct", "Headings, courses and exams"), ("accent", "Overdue")))
        cols += (f'<fieldset class="custom-mode" data-mode="{m}"><legend>{word}</legend>{pickers}'
                 f'<p class="warn" aria-live="polite">{e(" ".join(warns[m]))}</p></fieldset>')
    return ('<div class="custom-panel" id="custom-panel" data-kind="focus" hidden><h4 class="sub">Your theme</h4>'
            f'<div class="custom-modes">{cols}</div>'
            '<p class="hint">Changes apply as you pick. Birdbrain works out the softer shades from these four.</p></div>')


def _mcgraw_options(settings: Settings) -> str:
    """Under McGraw Hill Connect in Settings: how the student gets in, and whether Birdbrain may renew that by itself."""
    via = settings.mcgraw_via if settings.mcgraw_via in ("moodle", "direct") else "moodle"
    ways = "".join(f'<label><input type="radio" name="mcgraw-via" value="{v}"{" checked" if via == v else ""}><span>{e(t)}</span></label>'
                   for v, t in (("moodle", "From a link in a Moodle course"), ("direct", "At connect.mheducation.com")))
    used = (f' Last used: <b>{e(settings.mcgraw_launch_name)}</b>.' if settings.mcgraw_launch_name
            else " Birdbrain notes which link you click." if not settings.mcgraw_launch else "")
    return (f'<div class="sub-options" id="mcgraw-options"{"" if settings.scan_mcgraw else " hidden"}>'
            f'<fieldset class="field"><legend>How do you open it?</legend><div class="seg" role="radiogroup" '
            f'aria-label="How you open McGraw Hill Connect">{ways}</div></fieldset>'
            f'<div id="mcgraw-renew"{"" if via == "moodle" else " hidden"}>'
            '<p class="hint">Sign in to your school sites opens your Moodle course; click any McGraw Hill link in it once and '
            f'Birdbrain keeps the sign-in Moodle hands over.{used}</p>'
            f'<label class="check"><input type="checkbox" id="mcgraw-auto"{" checked" if settings.mcgraw_auto_renew else ""} '
            'aria-describedby="mcgraw-warn"><span>Renew the sign-in by itself</span></label>'
            '<p class="hint warn-note" id="mcgraw-warn">When Connect signs you out, Birdbrain re-opens the McGraw Hill link you last '
            'clicked in Moodle, in the background. McGraw Hill sees that as you opening that assignment, so it may show as '
            'opened or viewed, and your instructor may see that. Leave this off if that link is a timed quiz or exam.</p></div></div>')


def _addresses(settings: Settings) -> str:
    """Settings > Scanning: where Moodle and Outlook are, to fix an address mistyped at setup or move to another.
    The same fields as the welcome page; a changed address is saved, then signed in to."""
    outlook_on = settings.scan_outlook_mail or settings.scan_outlook_calendar
    account = "none" if not outlook_on else "personal" if "live.com" in settings.outlook_url else "school"
    accounts = "".join(
        f'<label><input type="radio" name="addr-account" value="{v}"{" checked" if v == account else ""}><span>{e(t)}</span></label>'
        for v, t in (("school", "School or work"), ("personal", "Personal (Outlook.com, Hotmail)"), ("none", "I don't use Outlook")))
    return ('<div class="set-sec" id="addr-sec"><h3>Moodle and Outlook</h3>'
            '<p class="hint">Where Birdbrain finds your courses and email. Paste the address of any page from your browser; '
            'Birdbrain keeps just the start.</p>'
            '<form id="addr-form" novalidate>'
            '<label class="field"><span>Moodle address</span><input id="addr-moodle" type="url" inputmode="url" autocomplete="off" '
            f'spellcheck="false" placeholder="https://moodle.yourschool.edu" value="{e(settings.moodle_url)}"></label>'
            '<fieldset class="field"><legend>Outlook account</legend>'
            f'<div class="seg" role="radiogroup" aria-label="Outlook account">{accounts}</div></fieldset>'
            f'<div id="addr-outlook-field"{"" if outlook_on else " hidden"}><label class="field"><span>Outlook address</span>'
            '<input id="addr-outlook" type="url" inputmode="url" autocomplete="off" spellcheck="false" '
            f'value="{e(settings.outlook_url)}"></label></div>'
            '<p class="form-error" id="addr-error" role="alert"></p>'
            '<div class="btn-row"><button type="submit" class="btn">Save addresses</button></div>'
            '<p class="hint" id="addr-msg" aria-live="polite"></p></form></div>')


# Settings is grouped by what you came to do, one tab each.
SETTINGS_TABS = (("look", "Look"), ("scanning", "Scanning"), ("courses", "Courses"), ("keywords", "Keywords"), ("app", "App"))

# Keyboard shortcuts. Each entry: the keys (alternatives, each a combination) and what they do. The first group works
# whenever no window is open and you aren't typing; the second while an item has focus.
KEYS = (("Anywhere", ((("N",),), "Add an item"), ((("S",),), "Open Settings"), ((("R",),), "Scan now"),
         ((("J",),), "Go to the first item"), ((("?",),), "Show these shortcuts"),
         ((("Ctrl", "Z"),), "Undo the last change"), ((("Esc",),), "Close a window")),
        ("On an item", ((("↓",), ("J",)), "Next item"), ((("↑",), ("K",)), "Previous item"),
         ((("←",), ("→",)), "The column beside"), ((("O",),), "Open it in Moodle or Outlook"),
         ((("A",),), "Archive it, or show it again"), ((("E",),), "Edit one you added"),
         ((("Space",),), "Tick it off")))


def _keys() -> str:
    def keys(alts):
        return '<span class="or">or</span>'.join("+".join(f"<kbd>{k}</kbd>" for k in combo) for combo in alts)
    groups = "".join(f'<h4 class="sub">{e(name)}</h4><dl class="keys">'
                     + "".join(f'<div><dt>{keys(alts)}</dt><dd>{e(what)}</dd></div>' for alts, what in rows) + '</dl>'
                     for name, *rows in KEYS)
    return (f'<div class="set-sec" id="keys-sec"><h3>Keyboard</h3>{groups}'
            '<p class="hint">Single keys work whenever no window is open and you aren\'t typing.</p></div>')


def _settings_dialog(b: Board, now: datetime, layout: str, photo, settings: Settings, p: dict) -> str:
    glass_layout = layout == "glass"
    layouts = "".join(f'<label><input type="radio" name="layout" value="{v}"><span>{label}</span></label>'
                      for v, label in theme.LAYOUT_NAMES.items())
    frames = "".join(f'<label><input type="radio" name="frame" value="{v}"><span>{label}</span></label>'
                     for v, label in (("wide", "Full width"), ("narrow", "Narrow, more photo")))
    frame_choice = ('<h4 class="sub">Frame</h4>'
                    f'<div class="seg frame" role="radiogroup" aria-label="Frame">{frames}</div>') if glass_layout else ""
    rows = "".join(
        f'<li data-code="{e(c)}"><input type="color" aria-label="Colour for {e(c)}">'
        f'<span class="cc">{e(c)}</span>'
        f'<input type="text" class="nick" maxlength="24" placeholder="Nickname" aria-label="Nickname for {e(c)}">'
        f'<button type="button" class="act reset">Reset</button><p class="warn" aria-live="polite"></p></li>'
        for c in b.courses)
    courses = (f'<ul class="courses">{rows}</ul>' if rows
               else '<p class="hint">Course codes appear here after the next scan.</p>')
    since = (now.date() - timedelta(days=30)).isoformat()
    live = ("scanning", "keywords", "app")   # these need Birdbrain running, so the read-only copy leaves them out
    tabs = "".join(
        f'<button type="button" role="tab" class="tab{" needs-app" if k in live else ""}" id="tab-{k}" aria-controls="pane-{k}" '
        f'aria-selected="{"true" if k == "look" else "false"}" tabindex="{0 if k == "look" else -1}">{label}</button>'
        for k, label in SETTINGS_TABS)

    def pane(k: str, body: str) -> str:
        return (f'<section class="pane{" needs-app" if k in live else ""}" id="pane-{k}" role="tabpanel" aria-labelledby="tab-{k}" '
                f'tabindex="0"{"" if k == "look" else " hidden"}>{body}</section>')

    look = (
        f'<div class="set-sec"><h3>Layout</h3><div class="seg layout" role="radiogroup" aria-label="Layout">{layouts}</div>'
        '<p class="hint">Glass sets your list on frosted panels overlooking the open sky. Focus is a calm, roomy page with '
        'nothing but your list. Each has its own themes, and a Custom one you make yourself.</p>'
        f'{frame_choice}</div>'
        '<div class="set-sec"><h3>Theme</h3>'
        f'<div class="themes" role="radiogroup" aria-label="Theme">{_theme_options(layout, photo, p)}</div>'
        f'{_custom_panel(layout, photo, p)}'
        '<label class="check"><input type="checkbox" id="follow-system">'
        "<span>Follow Windows' light and dark mode</span></label></div>")
    scanning = (
        '<div class="set-sec"><h3>Scan</h3>'
        f'<p class="hint">Birdbrain checks Moodle and Outlook every {settings.interval_minutes} minutes. '
        "Scan now if you're expecting something new; a full rescan also reads every course page.</p>"
        '<div class="btn-row"><button type="button" class="btn" id="scan-now" aria-keyshortcuts="R" title="Scan now (R)">Scan now</button>'
        '<button type="button" class="btn" id="scan-full">Full rescan of Moodle</button></div>'
        '<p class="hint" id="scan-now-msg" aria-live="polite"></p></div>'
        + _addresses(settings) +
        '<div class="set-sec"><h3>Other sites</h3>'
        '<p class="hint">If your courses use them, Birdbrain can read these too. Turn one on, then sign in to it below.</p>'
        f'<label class="check"><input type="checkbox" id="site-gradescope"{" checked" if settings.scan_gradescope else ""}>'
        '<span>Gradescope</span></label>'
        f'<label class="check"><input type="checkbox" id="site-mcgraw"{" checked" if settings.scan_mcgraw else ""}>'
        '<span>McGraw Hill Connect</span></label>'
        + _mcgraw_options(settings) +
        '<p class="hint" id="sites-msg" aria-live="polite"></p></div>'
        '<div class="set-sec"><h3>Sign in</h3>'
        '<p class="hint">Opens a window with Moodle, Outlook and any other sites you use. Sign in to each, and it closes '
        'by itself. Use it whenever a notification says you need to sign in again.</p>'
        '<div class="btn-row"><button type="button" class="btn" id="sign-in">Sign in to your school sites</button></div></div>'
        '<div class="set-sec"><h3>Older emails</h3>'
        '<p class="hint">Regular scans read your newest emails. To catch older ones, scan the inbox back to a date.</p>'
        '<div class="scan-row"><label class="field"><span>Scan back to</span>'
        f'<input type="date" id="scan-since" value="{since}" max="{now.date().isoformat()}"></label>'
        '<button type="button" class="btn" id="scan-go">Scan inbox</button>'
        '<button type="button" class="btn" id="scan-stop" hidden>Stop</button></div>'
        '<p class="hint" id="scan-msg" aria-live="polite"></p></div>')
    course_pane = ('<div class="set-sec"><p class="hint">Give each course code its own colour and a nickname. '
                   f'Changes apply right away.</p>{courses}</div>')
    keywords = (
        '<div class="set-sec"><p class="hint">Entries whose title or course contains one of these words move to Archived, '
        'at the bottom of your list. Nothing is deleted; remove a keyword and its entries come back.</p>'
        '<ul class="kw-list" id="kw-list"></ul>'
        '<form class="kw-add" id="kw-form" novalidate><label class="field"><span>Add a keyword</span>'
        '<input id="kw-input" maxlength="80" autocomplete="off"></label>'
        '<button type="submit" class="btn">Hide these entries</button></form>'
        '<p class="form-error" id="kw-error" role="alert"></p><p class="hint kw-msg" id="kw-msg" aria-live="polite"></p></div>')
    app = (
        '<div class="set-sec"><h3>Sounds</h3><div class="sound-row"><label class="check"><input type="checkbox" id="sound-on">'
        "<span>A soft call when something new is due, a chirp when you finish today's list</span></label>"
        '<button type="button" class="act" id="sound-test">Play the call</button></div></div>'
        + _keys() +
        '<div class="set-sec"><h3>Files</h3>'
        '<p class="hint">The settings file holds the scan interval, how far ahead to look and other options.</p>'
        '<div class="btn-row"><button type="button" class="btn" data-open="settings">Open settings file</button>'
        '<button type="button" class="btn" data-open="log">Open log</button></div></div>'
        '<div class="set-sec"><h3>Quit</h3>'
        '<p class="hint">Closing this window keeps Birdbrain scanning in the tray. Quit stops it until you start it again.</p>'
        '<div class="btn-row"><button type="button" class="btn danger" id="quit-app">Quit Birdbrain</button></div></div>')
    return (
        '<dialog id="settings" class="sheet-dialog" aria-labelledby="settings-title"><div class="sheet">'
        '<div class="sheet-head"><h2 id="settings-title">Settings</h2>'
        '<button type="button" class="act" data-close>Close</button></div>'
        f'<div class="tabs" role="tablist" aria-labelledby="settings-title">{tabs}</div>'
        + pane("look", look) + pane("scanning", scanning) + pane("courses", course_pane) + pane("keywords", keywords)
        + pane("app", app) + '</div></dialog>')


def _item_dialog(b: Board, now: datetime) -> str:
    types = "".join(f'<label><input type="radio" name="kind" value="{k}"{" checked" if k == "assignment" else ""}>'
                    f'<span>{label}</span></label>'
                    for k, label in (("assignment", "Assignment"), ("exam", "Exam"), ("quiz", "Quiz"),
                                     ("event", "Event")))
    options = "".join(f'<option value="{e(c)}">' for c in b.courses)
    return (
        '<dialog id="add-item" class="sheet-dialog" aria-labelledby="add-title">'
        '<form class="sheet" id="add-form" novalidate>'
        '<div class="sheet-head"><h2 id="add-title">Add item</h2>'
        '<button type="button" class="act" data-close>Close</button></div>'
        '<label class="field"><span>Title</span><input name="title" maxlength="200" autocomplete="off" required></label>'
        f'<fieldset class="field"><legend>Type</legend><div class="seg">{types}</div></fieldset>'
        '<div class="field-row">'
        f'<label class="field"><span>Due date</span><input type="date" name="date" value="{now.date().isoformat()}" required></label>'
        '<label class="field"><span>Time <em>optional</em></span><input type="time" name="time"></label></div>'
        '<label class="field"><span>Course <em>optional</em></span>'
        f'<input name="course" list="course-list" maxlength="40" autocomplete="off"></label><datalist id="course-list">{options}</datalist>'
        '<label class="field"><span>Notes <em>optional</em></span><input name="notes" maxlength="300" autocomplete="off"></label>'
        '<p class="form-error" role="alert"></p>'
        '<div class="actions-row"><button type="button" class="act" data-close>Cancel</button>'
        '<button type="submit" class="btn primary">Add item</button></div></form></dialog>')


def _grounds(p: dict) -> dict:
    """Each layout's ground colour, day and night, for the chosen themes: the photo's own colour behind Glass, the
    canvas in Focus. A layout switch crossfades through the new layout's ground."""
    def ground(layout: str, m: str) -> str:
        if layout == "glass":
            sc = custom.glass_scheme(p) if p["theme"] == theme.CUSTOM else glass.SCHEMES[p["theme"]]
            return sc[m]["bg"]
        if p["focus_theme"] == theme.CUSTOM:
            return custom.focus_tokens(custom.focus_picks(p)[m])["bg"]
        return theme.THEMES[p["focus_theme"]]["modes"][m]["bg"]
    return {layout: {m: ground(layout, m) for m in ("light", "dark")} for layout in theme.LAYOUTS}


def render(b: Board, settings: Settings, status: str, now: datetime, token: str = "", version: int = 0,
           prefs: dict | None = None, app_window: bool = False) -> str:
    prefs = prefs or prefs_mod.DEFAULTS
    mode = prefs["mode"] if prefs["mode"] in ("dark", "light") else theme.DEFAULT_MODE
    # "Match system" is resolved in the browser before the first paint.
    head_js = ("var r=document.documentElement;if(r.dataset.modePref==='system')"
               "r.dataset.mode=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';"
               # arriving from a layout switch (or the welcome page): start under the veil, which then lifts
               "try{var a=sessionStorage.getItem('bb-arrive');if(a!==null){sessionStorage.removeItem('bb-arrive');"
               "if(!matchMedia('(prefers-reduced-motion: reduce)').matches){r.classList.add('arriving');r.style.setProperty('--arrive',a||'transparent');}}}catch(e){}")
    layout = prefs["layout"]
    glass_layout = layout == "glass"
    # Photos come from Birdbrain's own server on the live page, and straight from disk in the read-only copy.
    photo = (lambda n: f"/bg/{n}.jpg?token={token}") if token else glass.file_url
    page_data = json.dumps({"prefs": prefs, "themes": list(prefs_mod.GLASS_THEMES if glass_layout else prefs_mod.FOCUS_THEMES),
                            "modes": list(theme.MODES), "grounds": _grounds(prefs),
                            "keywords": keyword_counts(b, settings.hidden_keywords), "wing": WING})
    page_data = page_data.replace("</", "<\\/")   # can't close the <script> early
    return "".join([
        f'<!doctype html><html lang="en"{' class="app-window"' if app_window and token else ''} data-frame="{e(prefs["frame"])}" data-layout="{e(layout)}" data-theme="{e(prefs_mod.active_theme(prefs))}" data-mode="{mode}" '
        f'data-mode-pref="{e(prefs["mode"])}">'
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta name="birdbrain-token" content="{e(token)}">' if token else "",
        f"<title>Birdbrain, {now:%a %b} {now.day}</title><script>{head_js}</script>",
        f"<style>{theme.font_face_css()}{theme.css_tokens()}{glass.css(photo) if glass_layout else CSS}"
        f"{TITLEBAR_CSS}{SCROLL_CSS}{MOTION_CSS}</style>",
        f'<style id="custom-css">{custom.css(prefs, photo)}</style></head>',
        f'<body class="{"live" if token else "static"}"><div class="wrap">',
        render_board(b, settings, status, now, version, prefs),
        f'</div>{_settings_dialog(b, now, layout, photo, settings, prefs)}{_item_dialog(b, now)}',
        '<div id="toast" role="status" aria-live="polite"></div><p id="announce" class="sr" aria-live="polite"></p>',
        '<div class="gscroll" aria-hidden="true"><i></i></div>',
        _TITLEBAR if app_window and token else "",
        f'<script type="application/json" id="page-data">{page_data}</script>',
        f"<script>{JS}</script><script>{CHROME_JS}</script></body></html>",
    ])


_TITLEBAR = ('<div class="titlebar"><div class="edge" data-edge="top"></div><div class="edge l" data-edge="topleft"></div>'
             '<div class="edge r" data-edge="topright"></div><div class="drag"></div>'
             '<button type="button" class="win-btn" id="win-min" aria-label="Minimize" title="Minimize">&#xE921;</button>'
             '<button type="button" class="win-btn" id="win-max" aria-label="Maximize" title="Maximize">'
             '<span class="max">&#xE922;</span><span class="res">&#xE923;</span></button>'
             '<button type="button" class="win-btn close" id="win-close" aria-label="Close" title="Close">&#xE8BB;</button></div>')


def render_setup(token: str, prefs: dict, app_window: bool = False, outlook_url: str = "") -> str:
    """First run, in two steps. 1: the Moodle and Outlook addresses, with a short guide to finding each (checked,
    not saved). 2: make it yours: Glass or Focus and a theme, and the page itself takes each choice as it's made.
    Start (POST /api/setup) saves both and moves on to signing in; Skip keeps the default look."""
    mode = prefs["mode"] if prefs["mode"] in ("dark", "light") else theme.DEFAULT_MODE
    head_js = ("var r=document.documentElement;if(r.dataset.modePref==='system')"
               "r.dataset.mode=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';")
    photo = (lambda n: f"/bg/{n}.jpg?token={token}") if token else glass.file_url
    account = "personal" if "live.com" in outlook_url else "school"
    accounts = "".join(
        f'<label><input type="radio" name="account" value="{v}"{" checked" if v == account else ""}><span>{label}</span></label>'
        for v, label in (("school", "School or work"), ("personal", "Personal (Outlook.com, Hotmail)"),
                         ("none", "I don't use Outlook")))
    art = photo(glass.photo_name("forest", "light", thumb=True))
    layouts = (
        '<label class="lp"><input type="radio" name="layout" value="glass">'
        f'<span class="lp-art glass-art" aria-hidden="true"{f" style=\"background-image:url(&quot;{e(art)}&quot;)\"" if art else ""}>'
        '<i></i><i></i><i></i></span><span class="lp-name">Glass</span>'
        '<span class="lp-desc">Your list on frosted panels overlooking the open sky, which changes with the time of day.</span></label>'
        '<label class="lp"><input type="radio" name="layout" value="focus">'
        '<span class="lp-art focus-art" aria-hidden="true"><i></i><i></i><i></i></span><span class="lp-name">Focus</span>'
        '<span class="lp-desc">A calm, roomy page with nothing but your list.</span></label>')
    data = json.dumps({"layout": prefs["layout"], "theme": prefs["theme"], "focus_theme": prefs["focus_theme"],
                       "mode": prefs["mode"]}).replace("</", "<\\/")
    return "".join([
        f'<!doctype html><html lang="en"{" class=\"app-window\"" if app_window and token else ""} data-layout="{e(prefs["layout"])}" '
        f'data-theme="{e(prefs_mod.active_theme(prefs))}" data-mode="{mode}" data-mode-pref="{e(prefs["mode"])}">',
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta name="birdbrain-token" content="{e(token)}">',
        f"<title>Welcome to Birdbrain</title><script>{head_js}</script>",
        f"<style>{theme.font_face_css()}{theme.css_tokens()}{glass.css(photo)}{TITLEBAR_CSS}{SCROLL_CSS}{SETUP_CSS}</style></head>",
        '<body class="live"><main class="setup">',
        '<p class="steps" aria-hidden="true"><span class="step-n">Step 1 of 2</span></p>',
        '<section id="step-connect" aria-labelledby="setup-title">',
        '<h1 id="setup-title" tabindex="-1">welcome to birdbrain</h1>',
        '<p class="lede">Birdbrain keeps one list of your assignments, exams and events from Moodle and Outlook. '
        'First, tell it where to find them.</p>',
        '<form id="setup-form" novalidate>',
        '<label class="field"><span>Moodle address</span><input name="moodle" type="url" inputmode="url" autocomplete="off" '
        'spellcheck="false" placeholder="https://moodle.yourschool.edu" required></label>',
        '<details class="guide"><summary>How do I find my Moodle address?</summary><ol>'
        '<li>Open Moodle in your web browser and sign in, as you usually do.</li>'
        '<li>Click the address bar at the top of the browser and copy the address (Ctrl+C).</li>'
        '<li>Paste it here (Ctrl+V). Any Moodle page works: Birdbrain keeps just the start, '
        'such as <b>https://moodle.lsu.edu</b>.</li></ol></details>',
        f'<fieldset class="field"><legend>Outlook account</legend>'
        f'<div class="seg" role="radiogroup" aria-label="Outlook account">{accounts}</div></fieldset>',
        f'<label class="field outlook-field"><span>Outlook address</span><input name="outlook" type="url" inputmode="url" '
        f'autocomplete="off" spellcheck="false" value="{e(outlook_url or "https://outlook.office.com")}"></label>',
        '<details class="guide outlook-field"><summary>How do I find my Outlook address?</summary><ol>'
        '<li>Open your email in a web browser (Outlook on the web, not the Outlook app).</li>'
        '<li>Copy the address from the address bar and paste it here. Birdbrain keeps just the start.</li>'
        '<li>School and work accounts usually start <b>https://outlook.office.com</b> or '
        '<b>https://outlook.cloud.microsoft</b>. Personal Outlook.com and Hotmail accounts start '
        '<b>https://outlook.live.com</b>. Choosing your account type above fills this in for you.</li></ol></details>',
        '<fieldset class="field sites"><legend>Also check <em>optional</em></legend>'
        '<label class="check"><input type="checkbox" name="gradescope"><span>Gradescope</span></label>'
        '<label class="check"><input type="checkbox" name="mcgraw"><span>McGraw Hill Connect</span></label>'
        '<p class="hint">Only if your courses use them. You sign in to each in the same window as Moodle.</p></fieldset>',
        '<p class="form-error" role="alert"></p>',
        '<div class="actions-row"><button class="btn primary" type="submit">Continue</button></div>',
        '</form></section>',
        '<section id="step-look" aria-labelledby="look-title" hidden>',
        '<h2 id="look-title" class="look-title" tabindex="-1">make it yours</h2>',
        '<p class="lede">Choose how your list looks. You can change it any time in Settings, where you can also '
        'make a theme of your own from your colours or photos.</p>',
        f'<fieldset class="field"><legend>Layout</legend><div class="layout-pick" role="radiogroup" aria-label="Layout">{layouts}</div></fieldset>',
        '<fieldset class="field"><legend>Theme</legend>',
        f'<div class="themes" data-for="glass" role="radiogroup" aria-label="Glass themes">'
        f'{_theme_options("glass", photo, prefs, "look-glass", with_custom=False)}</div>',
        f'<div class="themes" data-for="focus" role="radiogroup" aria-label="Focus themes">'
        f'{_theme_options("focus", photo, prefs, "look-focus", with_custom=False)}</div></fieldset>',
        '<label class="check"><input type="checkbox" id="follow-system">'
        "<span>Follow Windows' light and dark mode</span></label>",
        '<p class="form-error" role="alert"></p>',
        '<div class="actions-row"><button type="button" class="act" id="look-back">Back</button>'
        '<button type="button" class="act" id="look-skip">Skip for now</button>'
        '<button type="button" class="btn primary" id="look-go">Start Birdbrain</button></div>',
        '<p class="hint next">Next, a sign-in window opens for Moodle and Outlook. Sign in on their own pages as usual; '
        "Birdbrain never sees your password. The window closes by itself once you're done, and your list appears here.</p>",
        '</section></main>',
        '<div class="gscroll" aria-hidden="true"><i></i></div>',
        _TITLEBAR if app_window and token else "",
        f'<script type="application/json" id="setup-data">{data}</script>',
        f"<script>{CHROME_JS}</script><script>{SETUP_JS}</script></body></html>",
    ])


def write(store: Store, settings: Settings, status: str) -> tuple[str, int]:
    """Write the read-only copy (today.html); returns (path, count due today)."""
    now = datetime.now()
    b = build(store, settings, now)
    REPORT_PATH.write_text(render(b, settings, status, now, prefs=prefs_mod.load(store)), encoding="utf-8")
    return str(REPORT_PATH), b.due_today


CSS = """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:400 16px/1.5 "Birdbrain Sans","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body.static .needs-app{display:none!important}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
p,h1,h2,h3,h4,ul{margin:0;padding:0}ul{list-style:none}
::selection{background:color-mix(in srgb,var(--struct) 26%,transparent)}
:focus-visible{outline:2px solid var(--focus);outline-offset:3px;border-radius:4px}

/* Focus: one calm page. The list sits in a generous measure with wide margins; structure comes from space and a
   few light headings, never from boxes or rules. Type: 13 / 16 / 20 / 25 / 39px. Spacing: 8px steps, opening wide. */
.wrap{max-width:1240px;margin:0 auto;padding:clamp(40px,7vh,88px) clamp(24px,6vw,96px) 128px;container-type:inline-size}
.app-window .wrap{padding-top:clamp(48px,6.5vh,88px)}

/* the header: a small wordmark and quiet actions, then the day itself as the headline */
.top{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"title actions" "today today" "status status";align-items:center;row-gap:8px;margin-bottom:20px}
h1{grid-area:title;font-size:1rem;font-weight:700;letter-spacing:.02em;color:var(--struct);text-transform:lowercase}
.actions{grid-area:actions;display:flex;gap:4px}
.today{grid-area:today}
.today .date{font-size:2.441rem;font-weight:300;line-height:1.15;letter-spacing:-.01em;color:var(--head)}
/* the counts: a flat heat chip when above zero (Glass's colours, softened into the theme), plain at zero */
.counts{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;color:var(--muted)}
.counts .o,.counts .on{font-weight:700;padding:0 8px;border-radius:6px}
.counts [data-due=overdue].o{background:var(--accent);color:var(--accent-ink)}
.counts [data-due=today].on{background:var(--h-today);color:var(--h-today-ink)}
.counts [data-due=tomorrow].on{background:var(--h-tomorrow);color:var(--h-tomorrow-ink)}
.status{grid-area:status;font-size:.8125rem;color:var(--muted)}
.status.problem{color:var(--accent);font-weight:600}

/* words, not icons */
.act{position:relative;font:inherit;font-size:.8125rem;font-weight:600;color:var(--muted);background:none;border:0;padding:4px 6px;cursor:pointer;
 text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px}
.act::before{content:"";position:absolute;inset:-12px -4px}   /* a 44px hit area, same look */
.act:hover{color:var(--text)}
.act.del{color:var(--accent)}
.actions .act{font-size:1rem;min-height:44px;padding:8px 14px;color:var(--text);text-decoration:none;border-radius:8px;transition:background-color .15s}
.actions .act::before{display:none}
.actions .act:hover{background:var(--hover)}
.actions .act.strong{color:var(--struct)}
.btn{font:inherit;font-weight:600;min-height:44px;padding:0 20px;color:var(--struct);background:none;border:1px solid var(--line);border-radius:8px;cursor:pointer;
 transition:border-color .15s,background-color .15s}
.btn:hover{border-color:var(--struct);background:var(--hover)}
.btn.primary{background:var(--struct);border-color:var(--struct);color:var(--col)}
.btn.primary:hover{background:color-mix(in srgb,var(--struct) 86%,var(--text))}
.btn:disabled{opacity:.5;cursor:default}
.btn.danger{color:var(--accent);border-color:var(--accent)}

/* next exam and next quiz: one line under the day, each led by the chip its rows wear */
.next{display:flex;flex-wrap:wrap;gap:8px 48px;margin-bottom:40px}
.nx{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;min-width:0}
.nx .k{font-size:.8125rem;font-weight:700;line-height:1.5;text-transform:lowercase;padding:0 7px;border:1px solid var(--struct);border-radius:5px;color:var(--struct)}
.nx.exam .k{background:var(--struct);color:var(--bg)}
.nx .t{font-weight:600;line-height:1.4}
.nx.exam .t{font-weight:700}
.nx .none{color:var(--muted);font-style:italic}
.nx .meta{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;font-size:.8125rem;color:var(--muted)}

/* the three columns, straight on the page with wide gutters */
/* a thin rule in the structure colour down the middle of each gutter (across it, where the columns stack), so each
   category reads as its own; the columns stretch to the row so the rules run its full height */
.bands{display:grid;grid-template-columns:minmax(0,1fr);gap:72px;--rule:color-mix(in srgb,var(--struct) 30%,transparent)}
.band{position:relative;min-width:0}
.band+.band::before{content:"";position:absolute;top:-36px;left:0;right:0;height:1px;background:var(--rule);pointer-events:none}
@container (min-width:38rem){
.bands{grid-template-columns:repeat(2,minmax(0,1fr));gap:72px 56px}
.band:nth-child(2)::before{top:0;bottom:0;left:-28px;right:auto;width:1px;height:auto}
.band:nth-child(3){grid-column:1/-1}
.band:nth-child(3) ul{columns:2;column-gap:56px;column-rule:1px solid var(--rule)}   /* down one column, then the next: still in date order */
.band:nth-child(3) li{break-inside:avoid}}
@container (min-width:60rem){
.bands{grid-template-columns:repeat(3,minmax(0,1fr));gap:72px}
.band+.band::before{top:0;bottom:0;left:-36px;right:auto;width:1px;height:auto}
.band:nth-child(3){grid-column:auto}
.band:nth-child(3) ul{columns:auto}}
.band h2{display:flex;align-items:baseline;gap:12px;font-size:1.563rem;font-weight:300;line-height:1.2;color:var(--struct);text-transform:lowercase}
.n{font-size:.8125rem;font-weight:600;color:var(--muted);text-transform:none}
.grp{display:flex;align-items:center;gap:8px;font-size:1rem;font-style:italic;font-weight:400;color:var(--muted);text-transform:lowercase;margin:24px 0 4px}
.grp[data-due]{color:var(--text);font-weight:600}
.grp[data-due]::before{content:"";width:8px;height:8px;border-radius:50%;flex:none}
.grp[data-due=overdue]::before{background:var(--accent)}
.grp[data-due=today]::before{background:var(--h-today-dot)}
.grp[data-due=tomorrow]::before{background:var(--h-tomorrow-dot)}
.band h2+.grp,.band h2+ul,.band h2+.dayclear{margin-top:20px}
.empty{margin-top:24px;color:var(--muted);font-style:italic}

/* items: space between them, not lines; a soft wash under the pointer */
.row{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:6px;align-items:start;padding:10px 12px 10px 4px;margin:0 -12px 0 -4px;
 border-radius:8px;transition:background-color .15s ease-out}
.row:hover{background:var(--hover)}
.tickwrap{display:grid;place-items:center;width:44px;height:44px;margin:-11px -6px -11px -8px;cursor:pointer}
.tick{appearance:none;width:18px;height:18px;margin:0;border:1.5px solid var(--muted);border-radius:4px;display:grid;place-items:center;cursor:pointer;background:none}
.tick:checked{background:var(--text);border-color:var(--text)}
.tick:checked::after{content:"";width:5px;height:9px;border:solid var(--bg);border-width:0 2px 2px 0;transform:translateY(-1px) rotate(45deg)}
.tick:disabled{cursor:default;opacity:.6}
.t{display:block;font-size:1rem;line-height:1.4;color:var(--text);text-decoration:none;overflow-wrap:anywhere}
/* a title that opens Moodle or Outlook: a faint dotted underline at rest, solid under the pointer */
a.t{text-decoration:underline dotted color-mix(in srgb,var(--text) 40%,transparent);text-decoration-thickness:1px;text-underline-offset:4px}
a.t:hover{text-decoration-style:solid;text-decoration-color:currentColor}
.row.exam .t{font-weight:700}
.row.quiz .t{font-weight:600}
.row .meta{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin-top:4px;font-size:.8125rem;color:var(--muted)}
/* what it is: exams a solid chip in the structure colour, quizzes an outlined one; how soon is the date chip's job */
.kind{font-weight:700;line-height:1.5;padding:0 7px;border:1px solid var(--struct);border-radius:5px;color:var(--struct)}
.row.exam .kind{background:var(--struct);color:var(--bg)}
.code{font-weight:600;color:var(--struct);white-space:nowrap}
.code::before{content:"";display:none;width:7px;height:7px;margin-right:6px;border-radius:50%;background:var(--cc);vertical-align:.08em}
.code[style*="--cc"]::before{display:inline-block}   /* your course colour, once you've picked one */
.w.late{color:var(--accent);font-weight:700}
.w:empty{display:none}
[data-due=overdue]>.body .w,.nx[data-due=overdue] .w,[data-due=today]>.body .w,.nx[data-due=today] .w,
[data-due=tomorrow]>.body .w,.nx[data-due=tomorrow] .w{font-weight:700;padding:0 7px;border-radius:5px}
[data-due=overdue]>.body .w,.nx[data-due=overdue] .w{background:var(--accent);color:var(--accent-ink)}
[data-due=today]>.body .w,.nx[data-due=today] .w{background:var(--h-today);color:var(--h-today-ink)}
[data-due=tomorrow]>.body .w,.nx[data-due=tomorrow] .w{background:var(--h-tomorrow);color:var(--h-tomorrow-ink)}
.unsure{font-style:italic}
.row.past .t,.row.past .w{color:var(--muted)}
.row.is-done .t{color:var(--muted);text-decoration:line-through;font-weight:400}
.row.leaving{opacity:0;transform:translateX(6px);transition:opacity .18s ease-in,transform .18s ease-in}
.detail{font-size:.8125rem;color:var(--muted);margin-top:6px;max-width:36rem;overflow-wrap:anywhere}
.acts{display:inline-flex;gap:4px;margin-left:4px}
/* Archive: on every open item, shown under the pointer or while the row has keyboard focus (always, on touch) */
.act.arch{margin-left:auto;opacity:0;transition:opacity .15s ease-out}
.row:hover .act.arch,.row:focus-within .act.arch{opacity:1}
@media (hover:none){.act.arch{opacity:1}}
.kw-msg:empty{display:none}
.sub-options{margin:4px 0 8px 28px;padding-left:16px;border-left:1px solid var(--line)}
.sub-options .field{margin-bottom:4px}
.warn-note{color:var(--text);max-width:36rem}
/* the shortcut list: each key a small outlined cap */
kbd{display:inline-block;min-width:26px;padding:0 7px;font:inherit;font-size:.8125rem;font-weight:700;line-height:1.6;text-align:center;
 color:var(--text);background:var(--bg);border:1px solid var(--edge);border-radius:5px}
.keys{display:grid;gap:10px;margin:0 0 12px}
.keys div{display:grid;grid-template-columns:104px 1fr;align-items:baseline;gap:12px}
.keys dt{color:var(--muted);font-size:.8125rem}
.keys dd{margin:0}
.keys .or{margin:0 6px;font-size:.8125rem;color:var(--muted)}
#keys-sec .sub{margin:16px 0 8px}#keys-sec .sub:first-of-type{margin-top:0}

/* all clear, the first scan, the day-clear line, and the motion when items are ticked off */
.clear{display:grid;justify-items:start;gap:4px;margin-top:32px}
.perch{width:128px;height:80px;margin:0 0 12px -6px;color:var(--struct);overflow:visible}
.perch .bird{fill:currentColor}
.perch .branch,.perch .legs{fill:none;stroke:currentColor;stroke-linecap:round}.perch .branch{stroke-width:2.2;opacity:.55}.perch .legs{stroke-width:1.6}
.perch .wing{fill:none;stroke:var(--bg);stroke-width:1.4;stroke-linecap:round;opacity:.6}
.perched{transform-box:fill-box;transform-origin:50% 100%}
.clear-head{font-size:1.25rem;font-weight:300;line-height:1.2;color:var(--struct);text-transform:lowercase}
.clear-sub{color:var(--muted);max-width:28rem}
.clear-next{margin-top:8px}
.dayclear{display:flex;align-items:center;gap:8px;font-size:1rem;font-style:italic;color:var(--muted);text-transform:lowercase;margin:24px 0 4px}
.wingmark{width:18px;height:9px;flex:none;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round}
.clear.first .wingmark{width:34px;height:17px;margin:0 0 12px;stroke-width:1.8;color:var(--struct);transform-origin:50% 70%;animation:flap .5s ease-in-out infinite alternate}
.row.lifted{opacity:0}
.fly{position:fixed;z-index:40;margin:0;pointer-events:none}
.fly .row{margin:0;background:var(--col);outline:1px solid var(--line);box-shadow:0 10px 24px -10px rgba(0,0,0,.35),0 2px 6px -2px rgba(0,0,0,.18);transition:none}
.clear.waiting .perched,.dayclear.waiting .wingmark{opacity:0}
.flier{position:fixed;left:0;top:0;z-index:45;pointer-events:none;offset-rotate:0deg;color:var(--struct)}
.flier svg{display:block;width:34px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;
 transform-origin:50% 70%;animation:flap .26s ease-in-out infinite alternate}
@keyframes flap{to{transform:scaleY(-.6)}}

/* completed + archived: quiet disclosures at the foot of the page */
/* on the columns' own grid: Completed under Now, Archived under This week */
.bins{margin-top:120px;display:grid;grid-template-columns:minmax(0,1fr);gap:24px 72px;align-items:start}
.bin summary{position:relative;list-style:none;display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;cursor:pointer;width:fit-content;min-height:44px;padding:8px 0}
.bin summary::-webkit-details-marker{display:none}
.bin-title{font-size:1.25rem;font-weight:300;color:var(--struct);text-transform:lowercase}
.bin.archived .bin-title{color:var(--muted)}
.state{font-size:.8125rem;font-weight:600;color:var(--muted);text-decoration:underline;text-underline-offset:4px}
.state::after{content:"Show"}
.bin[open] .state::after{content:"Hide"}
.bin summary:hover .state{color:var(--text)}
.bin summary.pulse .bin-title{animation:pulse 1s ease-out}
@keyframes pulse{from{color:var(--accent)}}
.hint{font-size:.8125rem;color:var(--muted);margin:4px 0 16px;max-width:40rem}
/* each bin opens in place, down its own column, so opening one never moves the other */
.bin-grid{display:grid;grid-template-columns:minmax(0,1fr);align-items:start}
@container (min-width:38rem){.bins{grid-template-columns:repeat(2,minmax(0,1fr));column-gap:56px}}
@container (min-width:60rem){.bins{grid-template-columns:repeat(3,minmax(0,1fr));column-gap:72px}}

/* dialogs: a plain sheet */
.sheet-dialog{width:min(640px,calc(100vw - 32px));max-height:min(88vh,960px);padding:0;border:1px solid var(--line);border-radius:12px;background:var(--col);color:var(--text)}
.sheet-dialog::backdrop{background:rgba(10,12,20,.4)}
.sheet-dialog[open]{animation:sheet-in .2s ease-out}
@keyframes sheet-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.sheet{padding:32px 36px 36px;margin:0}
.sheet-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px}
.sheet-head h2{font-size:1.563rem;font-weight:300;color:var(--struct);text-transform:lowercase}
/* Settings: tabs across the top and one pane at a time; the dialog keeps its height as you switch */
#settings{height:min(88vh,720px);overflow:hidden}
#settings[open]{display:flex;flex-direction:column}
#settings .sheet{flex:1;min-height:0;display:flex;flex-direction:column;padding:0}
#settings .sheet-head{padding:28px 36px 12px;margin:0}
.tabs{flex:none;display:flex;gap:4px;padding:0 26px;border-bottom:1px solid var(--line);overflow-x:auto;scrollbar-width:none}
.tab{font:inherit;font-size:1rem;font-weight:600;color:var(--muted);background:none;border:0;border-bottom:2px solid transparent;margin-bottom:-1px;
 padding:0 10px;min-height:44px;min-width:44px;cursor:pointer;white-space:nowrap;transition:color .15s}
.tab:hover{color:var(--text)}
.tab[aria-selected=true]{color:var(--text);border-bottom-color:var(--struct)}
.tab:focus-visible{outline:2px solid var(--focus);outline-offset:-6px;border-radius:8px}
.pane{flex:1;min-height:0;overflow-y:auto;padding:0 36px 36px}
.pane:focus-visible{outline:2px solid var(--focus);outline-offset:-4px}
.pane::-webkit-scrollbar{width:14px}
.pane::-webkit-scrollbar-track{background:transparent;margin:8px 0}
.pane::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--struct) 38%,transparent);border:4px solid transparent;background-clip:padding-box;border-radius:999px}
.pane .set-sec:first-child{padding-top:24px}
.set-sec{padding-top:32px}
.set-sec h3{font-size:1rem;font-style:italic;font-weight:400;color:var(--muted);text-transform:lowercase;margin-bottom:12px}
.set-sec .sub{font-size:.8125rem;font-weight:600;color:var(--muted);margin:24px 0 8px}
.themes{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px 12px;margin-bottom:16px}
.theme-opt{position:relative;display:grid;gap:6px}
.theme-opt input,.seg input{position:absolute;opacity:0;pointer-events:none}
.swatch{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.half{position:relative;cursor:pointer;min-height:64px}
.half.tone{display:grid;grid-template-columns:1fr auto;align-content:space-between;align-items:center;gap:8px;padding:10px}
.tone-word{grid-column:1/-1;font-size:.8125rem;font-weight:700}
.tone-ink{height:5px;border-radius:3px}
.tone-dot{width:10px;height:10px;border-radius:50%}
.half:hover{filter:brightness(1.05)}
.half:has(input:checked){box-shadow:inset 0 0 0 2px #FFFFFF,inset 0 0 0 4px #000000}
.theme-name{font-size:.8125rem;color:var(--muted)}
.theme-opt:has(input:checked) .theme-name{color:var(--text);font-weight:600}
.theme-opt:has(input:focus-visible) .swatch{outline:2px solid var(--focus);outline-offset:3px}
.custom-panel{margin:0 0 16px;padding:20px 24px 16px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}
.custom-panel .sub{margin-top:0}
.custom-modes{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px 32px}
.custom-mode{border:0;padding:0;margin:0;display:grid;align-content:start;min-width:0}
.custom-mode legend{font-size:.8125rem;font-weight:700;color:var(--text);padding:0;margin-bottom:4px}
.custom-mode .warn{font-size:.8125rem;color:var(--accent);margin-top:4px}.custom-mode .warn:empty{display:none}
.cpick{display:flex;align-items:center;gap:12px;min-height:44px;cursor:pointer}
.cpick input[type=color]{appearance:none;-webkit-appearance:none;flex:none;width:44px;height:44px;padding:7px;margin:0 -7px;border:0;background:none;cursor:pointer}
.cpick input[type=color]::-webkit-color-swatch-wrapper{padding:0}
.cpick input[type=color]::-webkit-color-swatch{border:1px solid var(--line);border-radius:8px}
.cpick em{font-style:normal;font-size:.8125rem;color:var(--muted)}
.seg{display:flex;flex-wrap:wrap;gap:4px 24px}
.seg label{position:relative;cursor:pointer}
.seg span{display:inline-block;min-width:44px;padding:12px 6px;margin:0 -6px;color:var(--muted);font-weight:400}
.seg label:hover span{color:var(--text)}
.seg input:checked+span{color:var(--text);font-weight:700;text-decoration:underline;text-decoration-color:var(--struct);text-decoration-thickness:2px;text-underline-offset:6px}
.seg label:has(input:focus-visible){outline:2px solid var(--focus);outline-offset:2px}
fieldset.field{border:0;padding:0;margin:0 0 16px}
.field{display:grid;gap:6px;margin:0 0 16px;min-width:0}
.field>span,.field legend{font-size:.8125rem;font-weight:600;color:var(--muted);padding:0}
.field em{font-style:italic;font-weight:400}
.field input{font:inherit;font-size:1rem;color:var(--text);background:var(--bg);border:1px solid var(--edge);border-radius:8px;padding:10px 12px;min-height:44px;min-width:0;width:100%}
.field input:focus{border-color:var(--struct);outline:2px solid var(--focus);outline-offset:1px}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-error{font-size:1rem;color:var(--accent);margin-bottom:8px}.form-error:empty{display:none}
.actions-row{display:flex;justify-content:flex-end;align-items:center;gap:16px;margin-top:8px}
.scan-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px}.scan-row .field{margin:0;flex:1 1 200px}
.btn-row{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 8px}
.check{display:flex;align-items:center;gap:10px;min-height:44px;cursor:pointer;color:var(--text)}
.check input{width:18px;height:18px;margin:0;flex:none;accent-color:var(--struct)}
.sound-row{display:flex;flex-wrap:wrap;align-items:center;gap:0 18px}
:root{--tb-fg:var(--text);--tb-hover:color-mix(in srgb,var(--text) 12%,transparent);--tb-scrolled:color-mix(in srgb,var(--bg) 88%,transparent);
 --sb-track:transparent;--sb-track-edge:transparent;--sb-blur:none;--sb-bevel:none;
 --sb-thumb:color-mix(in srgb,var(--struct) 38%,transparent);--sb-thumb-hover:color-mix(in srgb,var(--struct) 62%,transparent);--sb-thumb-edge:transparent}
.sheet-dialog::-webkit-scrollbar{width:14px}
.sheet-dialog::-webkit-scrollbar-track{background:transparent;margin:12px 0}
.sheet-dialog::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--struct) 38%,transparent);border:4px solid transparent;background-clip:padding-box;border-radius:999px}
.sheet-dialog::-webkit-scrollbar-thumb:hover{background-color:color-mix(in srgb,var(--struct) 62%,transparent)}
.kw-list li{display:flex;flex-wrap:wrap;align-items:center;gap:4px 14px;padding:8px 0;border-bottom:1px solid var(--line)}
.kw{font-weight:600}.kw-n{flex:1;font-size:.8125rem;color:var(--muted)}.kw-empty{color:var(--muted);font-style:italic;border:0!important}
.kw-add{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px;margin-top:12px}.kw-add .field{margin:0;flex:1 1 220px}
.gone{font-size:1.25rem;color:var(--muted);margin:64px 0}
.courses li{display:grid;grid-template-columns:32px minmax(96px,auto) 1fr auto;grid-template-areas:"color code nick reset" ". warn warn warn";align-items:center;column-gap:12px;padding:6px 0}
.courses input[type=color]{grid-area:color;appearance:none;-webkit-appearance:none;width:44px;height:44px;padding:8px;margin:-8px;border:0;border-radius:50%;background:none;cursor:pointer}
.courses input[type=color]::-webkit-color-swatch-wrapper{padding:0}
.courses input[type=color]::-webkit-color-swatch{border:1px solid var(--line);border-radius:50%}
.courses li.unset input[type=color]::-webkit-color-swatch{background:transparent!important;border:1.5px dashed var(--muted)}   /* no colour picked */
.cc{grid-area:code;font-size:1rem;font-weight:600;color:var(--struct);white-space:nowrap}
.nick{grid-area:nick;min-width:0;width:100%;font:inherit;font-size:1rem;color:var(--text);background:var(--bg);border:1px solid var(--edge);border-radius:8px;padding:8px 10px}
.nick::placeholder{color:var(--muted)}
.nick:focus{border-color:var(--struct);outline:2px solid var(--focus);outline-offset:1px}
.reset{grid-area:reset}
.reset:disabled{opacity:.45;cursor:default;text-decoration:none}
.courses .warn{grid-area:warn;font-size:.8125rem;color:var(--accent);margin-top:2px}.courses .warn:empty{display:none}
#toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,10px);max-width:calc(100vw - 32px);padding:12px 18px;border-radius:10px;background:var(--text);color:var(--bg);font-weight:600;
 opacity:0;pointer-events:none;transition:opacity .2s ease-out,transform .2s ease-out}
#toast.show{opacity:1;transform:translate(-50%,0)}
#toast.has-action.show{pointer-events:auto;display:flex;align-items:center;gap:16px}
.toast-undo{font:inherit;font-weight:700;color:var(--bg);background:none;border:1px solid var(--bg);border-radius:6px;min-height:32px;padding:0 12px;cursor:pointer}
@media (max-width:760px){
.wrap{padding:32px 20px 96px}.app-window .wrap{padding-top:52px}
.top{margin-bottom:16px}.today .date{font-size:1.953rem}
.next{margin-bottom:40px;gap:8px 32px}.bins{margin-top:88px}
.sheet{padding:20px}.field-row{grid-template-columns:1fr}
#settings{height:calc(100vh - 32px)}#settings .sheet-head{padding:20px 20px 8px}.tabs{padding:0 10px;gap:0;justify-content:space-between}.tab{padding:0 5px}.pane{padding:0 20px 24px}
.courses li{grid-template-columns:32px 1fr auto;grid-template-areas:"color code reset" ". nick nick" ". warn warn";row-gap:6px}}
.no-anim *{transition:none!important}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

TITLEBAR_CSS = """
/* the app window's own title bar (appwindow.py removes Windows' one): see-through, frosted once you scroll */
.titlebar{display:none}
.app-window .titlebar{display:flex;position:fixed;top:0;left:0;right:0;height:32px;z-index:40;user-select:none;-webkit-user-select:none;background:var(--tb-bg,transparent);transition:background-color .2s ease-out}
.app-window.scrolled .titlebar{background:var(--tb-scrolled);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}
.titlebar .drag{flex:1}
.titlebar .edge{position:absolute;top:0;left:0;right:0;height:5px;cursor:n-resize;z-index:1}
.titlebar .edge[data-edge=top]{right:138px}   /* leaves the window buttons their full height */
.titlebar .edge.l,.titlebar .edge.r{width:10px}.titlebar .edge.l{cursor:nw-resize}.titlebar .edge.r{left:auto;cursor:ne-resize}
.maximized .titlebar .edge{display:none}
.win-btn{width:46px;height:32px;border:0;border-radius:0;padding:0;background:transparent;color:var(--tb-fg);text-shadow:var(--tb-shadow,none);font:10px/1 "Segoe Fluent Icons","Segoe MDL2 Assets",sans-serif;display:grid;place-items:center;cursor:default;transition:background-color .1s}
.win-btn:hover{background:var(--tb-hover)}
.win-btn.close:hover{background:#C42B1C;color:#FFFFFF}
.win-btn:focus-visible{outline:2px solid currentColor;outline-offset:-4px;border-radius:0}
.win-btn .res{display:none}.maximized .win-btn .max{display:none}.maximized .win-btn .res{display:inline}
@media (prefers-reduced-motion:reduce){.titlebar,.win-btn{transition:none}}
"""

MOTION_CSS = """
/* motion shared by both layouts: sheets closing, and the veil a layout switch crossfades through */
.sheet-dialog[open]::backdrop{animation:veil-in .2s ease-out}
.sheet-dialog[open].closing{animation:sheet-out .16s cubic-bezier(.4,0,1,1) forwards}
.sheet-dialog.closing::backdrop{animation:veil-fade .16s ease-in forwards}
@keyframes sheet-out{to{opacity:0;transform:translateY(8px) scale(.985)}}
@keyframes veil-in{from{opacity:0}}
@keyframes veil-fade{to{opacity:0}}
.veil{position:fixed;inset:0;z-index:39;pointer-events:none;opacity:0}   /* under the window's own title bar (40) */
html.arriving::after{content:"";position:fixed;inset:0;z-index:39;pointer-events:none;background:var(--arrive);
 animation:veil-lift .55s cubic-bezier(.16,1,.3,1) .06s forwards}
html.arriving .wrap{animation:arrive .6s cubic-bezier(.16,1,.3,1) .04s both}
@keyframes veil-lift{to{opacity:0}}
@keyframes arrive{from{opacity:0;transform:translateY(12px)}}
@media (prefers-reduced-motion:reduce){html.arriving::after{display:none}}
/* a bin opening or closing: clipped while it grows or folds, and "Show" as soon as it starts to close */
.bin.moving{overflow:hidden}
.bin.closing .state::after{content:"Show"}
"""

SCROLL_CSS = """
/* the page's own scrollbar (Windows' one is hidden): it floats over the page, starts under the title bar,
   rests faintly, and comes forward while you scroll or point at it. Colours come from the layout (--sb-*). */
html{scrollbar-width:none}html::-webkit-scrollbar{display:none}
.gscroll{display:none;position:fixed;top:8px;bottom:8px;right:4px;width:10px;z-index:45;border-radius:999px;
 background:var(--sb-track);border:1px solid var(--sb-track-edge);-webkit-backdrop-filter:var(--sb-blur);backdrop-filter:var(--sb-blur);
 opacity:.6;transform-origin:right center;transition:opacity .25s ease-out,transform .15s ease-out}
.app-window .gscroll{top:38px}
.gscroll.on{display:block}
.gscroll.moving,.gscroll:hover,.gscroll.active{opacity:1}
.gscroll:hover,.gscroll.active{transform:scaleX(1.4)}
.gscroll i{position:absolute;left:1px;right:1px;top:0;border-radius:999px;background:var(--sb-thumb);border:1px solid var(--sb-thumb-edge);
 box-shadow:var(--sb-bevel);-webkit-backdrop-filter:var(--sb-blur);backdrop-filter:var(--sb-blur);transition:background-color .15s}
.gscroll i:hover,.gscroll.active i{background:var(--sb-thumb-hover)}
@media (prefers-reduced-motion:reduce){.gscroll,.gscroll i{transition:none}}
"""

SETUP_CSS = """
/* the welcome page: one panel over the photo (Glass) or on the page (Focus), in two steps */
.setup{width:min(680px,calc(100% - 32px));margin:64px auto;padding:28px 36px 32px;background:var(--g-glass);
 -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);outline:2px solid var(--g-edge);border-radius:10px;
 box-shadow:inset 3px 3px 6px rgba(255,255,255,.4),inset -3px -3px 6px rgba(0,0,0,.4)}
.steps{text-align:center;font-size:.8125rem;font-weight:600;color:var(--g-t2);margin:0 0 12px}
.setup h1,.look-title{font-size:2.5rem;font-weight:700;line-height:1.1;color:var(--g-title);text-transform:lowercase;text-align:center;margin:0}
.setup h1:focus,.look-title:focus{outline:none}
.setup .lede{text-align:center;color:var(--g-t2);margin:.6rem auto 1.8rem;max-width:34rem}
.setup .field{margin-bottom:.6rem}
.guide{margin:0 0 24px;font-size:1rem;line-height:1.5;color:var(--g-t2)}
.guide summary{cursor:pointer;width:fit-content;min-height:32px;padding:4px 0;color:var(--g-t1);font-weight:600;
 text-decoration:underline;text-underline-offset:3px}
.guide ol{margin:.4rem 0 0;padding:.8rem 1rem .8rem 2.2rem;display:grid;gap:.45rem;background:var(--g-pane);
 border:1px solid var(--g-line);border-radius:8px}
.guide b{color:var(--g-t1);font-weight:700;overflow-wrap:anywhere}
.setup .actions-row{margin-top:.2rem}
.setup .next{margin:1.1rem 0 0;max-width:none}
[hidden]{display:none!important}
/* step 2: Glass or Focus, then a theme */
.layout-pick{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:12px}
.lp{position:relative;display:grid;gap:4px;padding:12px 12px 14px;border:1px solid var(--g-line);border-radius:10px;cursor:pointer;
 transition:border-color .15s,background-color .15s}
.lp input{position:absolute;opacity:0;pointer-events:none}
.lp:hover{background:rgba(255,255,255,.06)}
.lp:has(input:checked){border-color:var(--g-t1);box-shadow:inset 0 0 0 1px var(--g-t1)}
.lp:has(input:focus-visible){outline:2px solid var(--g-focus);outline-offset:3px}
.lp-art{display:grid;grid-template-columns:1fr 1.35fr 1fr;gap:6px;height:88px;padding:12px;border-radius:6px;margin-bottom:6px;
 background:#7FA3D2 center/cover no-repeat}
.lp-art i{display:block;border-radius:4px}
.glass-art i{background:rgba(36,41,51,.66);box-shadow:inset 0 0 0 1px rgba(255,255,255,.45)}
.focus-art{background:#F6F8F4;box-shadow:inset 0 0 0 1px rgba(0,0,0,.08);gap:14px;padding:16px 18px}
.focus-art i{border-radius:0;background:linear-gradient(#2C5A43,#2C5A43) 0 0/60% 3px no-repeat,
 linear-gradient(#16211A,#16211A) 0 14px/100% 2px no-repeat,linear-gradient(#16211A,#16211A) 0 26px/80% 2px no-repeat,
 linear-gradient(#16211A,#16211A) 0 38px/90% 2px no-repeat,linear-gradient(#A3261C,#A3261C) 0 50px/40% 2px no-repeat}
.lp-name{font-weight:700;color:var(--g-t1)}
.lp-desc{font-size:.8125rem;color:var(--g-t2)}
.setup .themes{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px 12px;margin:4px 0 8px}
.half.tone{display:grid;grid-template-columns:1fr auto;align-content:space-between;align-items:center;gap:8px;padding:10px;min-height:64px}
.tone-word{grid-column:1/-1;font-size:.8125rem;font-weight:700}
.tone-ink{height:5px;border-radius:3px}
.tone-dot{width:10px;height:10px;border-radius:50%}
/* Focus, previewed in place: the same page, flat, in the chosen theme's colours */
:root[data-layout=focus][data-theme][data-mode]{--g-photo:none;--g-bg:var(--bg);--g-glass:var(--col);--g-sheet:var(--col);--g-t1:var(--text);
 --g-t2:var(--muted);--g-line:var(--line);--g-rule:var(--line);--g-edge:var(--line);--g-pane:var(--bg);--g-title:var(--head);--g-focus:var(--focus);
 --tb-fg:var(--text);--tb-bg:transparent;--tb-shadow:none;--tb-hover:color-mix(in srgb,var(--text) 12%,transparent)}
[data-layout=focus] .setup{-webkit-backdrop-filter:none;backdrop-filter:none;outline:1px solid var(--line);border-radius:14px;padding:36px 44px 40px;
 box-shadow:none;background:var(--col)}
[data-layout=focus] .setup h1,[data-layout=focus] .look-title{font-weight:300;color:var(--struct)}
[data-layout=focus] .field input{color:var(--text);background:var(--bg);border-color:var(--line)}
[data-layout=focus] .field input:focus{border-color:var(--struct)}
[data-layout=focus] .field input::placeholder{color:var(--muted)}
[data-layout=focus] .btn{color:var(--struct);background:none;border-color:var(--line)}
[data-layout=focus] .btn:hover{color:var(--struct);background:var(--hover);border-color:var(--struct);box-shadow:none}
[data-layout=focus] .btn.primary,[data-layout=focus] .btn.primary:hover{background:var(--struct);border-color:var(--struct);color:var(--col)}
[data-layout=focus] .seg span{color:var(--muted);background:none;border-color:var(--line)}
[data-layout=focus] .seg label:hover span{color:var(--text);background:var(--hover);box-shadow:none}
[data-layout=focus] .seg input:checked+span{color:var(--col);background:var(--struct);border-color:var(--struct)}
[data-layout=focus] .check input{accent-color:var(--struct)}
[data-layout=focus] .form-error{color:var(--accent)}
[data-layout=focus] .lp:hover{background:var(--hover)}
[data-layout=focus] .lp:has(input:checked){border-color:var(--struct);box-shadow:inset 0 0 0 1px var(--struct)}
@media (max-width:560px){.setup,[data-layout=focus] .setup{padding:22px 18px}.setup h1,.look-title{font-size:2rem}}
"""

SETUP_JS = """(function(){
var root=document.documentElement,form=document.getElementById('setup-form'),err=form.querySelector('.form-error'),f=form.elements,
    TOKEN=document.querySelector('meta[name="birdbrain-token"]').content,
    SITES={school:'https://outlook.office.com',personal:'https://outlook.live.com'},
    connect=document.getElementById('step-connect'),look=document.getElementById('step-look'),stepN=document.querySelector('.step-n'),
    lookErr=look.querySelector('.form-error'),go=document.getElementById('look-go'),follow=document.getElementById('follow-system'),
    media=matchMedia('(prefers-color-scheme: light)'),pick=JSON.parse(document.getElementById('setup-data').textContent),addr=null;
function post(body){return fetch('/api/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Birdbrain-Token':TOKEN},
  body:JSON.stringify(body)}).then(function(res){return res.json().catch(function(){return {};}).then(function(j){
    if(!res.ok)throw new Error(j.error||('Error '+res.status));return j;});});}
function show(step){connect.hidden=step!=='connect';look.hidden=step!=='look';stepN.textContent='Step '+(step==='connect'?1:2)+' of 2';
  scrollTo(0,0);document.getElementById(step==='connect'?'setup-title':'look-title').focus();}
/* step 1: where Moodle and Outlook are (checked here, saved with step 2) */
function sync(){var kind=f.account.value,now=f.outlook.value.trim();
  document.querySelectorAll('.outlook-field').forEach(function(el){el.hidden=kind==='none';});
  if(SITES[kind]&&(!now||now===SITES.school||now===SITES.personal))f.outlook.value=SITES[kind];}
form.querySelectorAll('input[name=account]').forEach(function(r){r.addEventListener('change',sync);});
sync();
form.addEventListener('submit',function(ev){ev.preventDefault();err.textContent='';
  var body={moodle:f.moodle.value.trim(),outlook:f.outlook.value.trim(),no_outlook:f.account.value==='none',
    gradescope:f.gradescope.checked,mcgraw:f.mcgraw.checked};
  if(!body.moodle){err.textContent='Enter your Moodle address.';f.moodle.focus();return;}
  var btn=form.querySelector('button[type=submit]');btn.disabled=true;btn.textContent='Checking…';
  post(Object.assign({check:true},body)).then(function(){addr=body;show('look');})
    .catch(function(e){err.textContent=e.message;}).then(function(){btn.disabled=false;btn.textContent='Continue';});});
/* step 2: make it yours. The page itself takes each choice as it's made. */
function paint(){root.classList.add('no-anim');root.dataset.layout=pick.layout;
  root.dataset.theme=pick.layout==='glass'?pick.theme:pick.focus_theme;root.dataset.modePref=pick.mode;
  root.dataset.mode=pick.mode==='system'?(media.matches?'light':'dark'):pick.mode;
  look.querySelectorAll('input[name=layout]').forEach(function(r){r.checked=r.value===pick.layout;});
  look.querySelectorAll('.themes').forEach(function(g){g.hidden=g.dataset.for!==pick.layout;});
  look.querySelectorAll('input[name=look-glass]').forEach(function(r){r.checked=r.value===pick.theme+':'+root.dataset.mode;});
  look.querySelectorAll('input[name=look-focus]').forEach(function(r){r.checked=r.value===pick.focus_theme+':'+root.dataset.mode;});
  follow.checked=pick.mode==='system';
  requestAnimationFrame(function(){requestAnimationFrame(function(){root.classList.remove('no-anim');});});}
look.querySelectorAll('input[name=layout]').forEach(function(r){r.addEventListener('change',function(){pick.layout=r.value;paint();});});
[['look-glass','theme'],['look-focus','focus_theme']].forEach(function(kind){
  look.querySelectorAll('input[name='+kind[0]+']').forEach(function(r){r.addEventListener('change',function(){
    var v=r.value.split(':');pick[kind[1]]=v[0];pick.mode=v[1];paint();});});});
follow.addEventListener('change',function(){pick.mode=follow.checked?'system':root.dataset.mode;paint();});
media.addEventListener('change',function(){if(pick.mode==='system')paint();});
function finish(keep){lookErr.textContent='';go.disabled=true;go.textContent='Starting…';
  post(Object.assign({},addr,keep?{layout:pick.layout,theme:pick.theme,focus_theme:pick.focus_theme,mode:pick.mode}:{}))
    .then(function(){   /* hand over to the list through the veil its page lifts on arrival */
      var ground=getComputedStyle(root).getPropertyValue(keep&&pick.layout==='focus'?'--bg':'--g-bg').trim();
      try{sessionStorage.setItem('bb-arrive',ground);}catch(e){}
      if(matchMedia('(prefers-reduced-motion: reduce)').matches){location.reload();return;}
      document.querySelector('.setup').animate([{opacity:1,transform:'none'},{opacity:0,transform:'translateY(10px)'}],
        {duration:240,easing:'cubic-bezier(.4,0,1,1)',fill:'forwards'}).finished.then(function(){location.reload();});})
    .catch(function(e){lookErr.textContent=e.message;go.disabled=false;go.textContent='Start Birdbrain';});}
go.addEventListener('click',function(){finish(true);});
document.getElementById('look-skip').addEventListener('click',function(){finish(false);});
document.getElementById('look-back').addEventListener('click',function(){show('connect');});
paint();f.moodle.focus();
})();"""


CHROME_JS = """(function(){   /* the scrollbar and the app window's title bar, on every page */
var root=document.documentElement;
/* the page's own scrollbar: the thumb follows the page; drag it, or click the rail to page up or down */
(function(){
  var bar=document.querySelector('.gscroll');if(!bar)return;
  var thumb=bar.firstElementChild,se=document.scrollingElement,drag=null,resting,raf=0,
      smooth=matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
  function metrics(){var track=bar.clientHeight,view=se.clientHeight,full=se.scrollHeight,
    h=Math.max(36,track*view/Math.max(full,1));return {track:track,h:Math.min(h,track),max:full-view};}
  function paint(){raf=0;var m=metrics();bar.classList.toggle('on',m.max>1);if(m.max<=1)return;
    thumb.style.height=m.h+'px';thumb.style.transform='translateY('+((m.track-m.h)*se.scrollTop/m.max)+'px)';}
  function later(){if(!raf)raf=requestAnimationFrame(paint);}
  addEventListener('scroll',function(){later();bar.classList.add('moving');clearTimeout(resting);
    resting=setTimeout(function(){bar.classList.remove('moving');},900);},{passive:true});
  addEventListener('resize',later);
  if(window.ResizeObserver)new ResizeObserver(later).observe(document.body);   /* refreshes, bins opening */
  thumb.addEventListener('pointerdown',function(ev){if(ev.button!==0)return;ev.preventDefault();
    var m=metrics();drag={y:ev.clientY,top:se.scrollTop,per:m.max/Math.max(1,m.track-m.h)};
    thumb.setPointerCapture(ev.pointerId);bar.classList.add('active');});
  thumb.addEventListener('pointermove',function(ev){if(drag)se.scrollTop=drag.top+(ev.clientY-drag.y)*drag.per;});
  function end(){drag=null;bar.classList.remove('active');}
  thumb.addEventListener('pointerup',end);thumb.addEventListener('pointercancel',end);
  bar.addEventListener('pointerdown',function(ev){if(ev.target!==bar||ev.button!==0)return;
    var r=thumb.getBoundingClientRect();se.scrollBy({top:(ev.clientY<r.top?-1:1)*se.clientHeight*.9,behavior:smooth});});
  paint();
})();

/* the app window's own title bar: a press on it moves the window the way Windows' own bar would */
if(root.classList.contains('app-window')){
  var tb=document.querySelector('.titlebar'),lastDown=0;
  function win(name,arg){var a=window.pywebview&&window.pywebview.api;if(a&&a[name])return arg===undefined?a[name]():a[name](arg);}
  window.birdbrainWindow={maximized:function(on){root.classList.toggle('maximized',!!on);
    document.getElementById('win-max').setAttribute('aria-label',on?'Restore':'Maximize');
    document.getElementById('win-max').title=on?'Restore':'Maximize';}};
  tb.querySelector('.drag').addEventListener('mousedown',function(ev){if(ev.button!==0)return;
    var now=Date.now();if(now-lastDown<400){lastDown=0;win('toggle_maximize');return;}lastDown=now;win('drag','move');});
  tb.querySelectorAll('[data-edge]').forEach(function(el){el.addEventListener('mousedown',function(ev){
    if(ev.button===0)win('drag',el.dataset.edge);});});
  document.getElementById('win-min').addEventListener('click',function(){win('minimize');});
  document.getElementById('win-max').addEventListener('click',function(){win('toggle_maximize');});
  document.getElementById('win-close').addEventListener('click',function(){win('close');});
  addEventListener('scroll',function(){root.classList.toggle('scrolled',scrollY>4);},{passive:true});
  addEventListener('pywebviewready',function(){var a=window.pywebview.api;
    a.framed().then(function(ok){if(!ok)root.classList.remove('app-window');});
    a.is_maximized().then(function(m){birdbrainWindow.maximized(m);});});
}
})();"""

JS = """(function(){
var root=document.documentElement,wrap=document.querySelector('.wrap');
function meta(n){var m=document.querySelector('meta[name="'+n+'"]');return m?m.content:'';}
var TOKEN=meta('birdbrain-token'),LIVE=!!TOKEN;
var DATA=JSON.parse(document.getElementById('page-data').textContent),PREFS=DATA.prefs;
function version(){var m=document.getElementById('board-meta');return m?m.dataset.version:'';}

/* --- talking to Birdbrain ------------------------------------------------- */
var GONE='Birdbrain restarted. Reopen the list from the tray icon.';
function api(path,body){
  return fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Birdbrain-Token':TOKEN},
    body:JSON.stringify(body||{})}).then(function(r){
    return r.json().catch(function(){return {};}).then(function(j){
      if(r.status===403)throw new Error(GONE);
      if(!r.ok)throw new Error(j.error||('Error '+r.status));return j;});});
}
function status(){return fetch('/api/status?token='+encodeURIComponent(TOKEN)).then(function(r){
  if(!r.ok)throw new Error('offline');return r.json();});}
/* Refreshing rebuilds the list, so remember where keyboard focus was and put it back (or on the row named). */
function focusTarget(){var a=document.activeElement;if(!a||a===document.body||!wrap.contains(a))return null;
  var r=a.closest('.row[data-id]');return {id:r?r.dataset.id:null,sel:a.id?'#'+CSS.escape(a.id):null,
    part:a.classList.contains('tick')?'.tick':a.matches('a.t')?'a.t':a.classList.contains('more')?'.act.more':'.tick'};}
function restoreFocus(f){if(!f)return;var el=null;
  [f.id,f.fallback].forEach(function(id){if(el||!id)return;var row=wrap.querySelector('.row[data-id="'+CSS.escape(id)+'"]');
    if(row)el=row.querySelector(f.part||'.tick')||row.querySelector('.tick');});
  if(!el&&f.sel)el=wrap.querySelector(f.sel);
  if(el)el.focus();}
/* The status line is rebuilt too, so a new problem (not just a new "Updated" time) is read out from a region that stays. */
function problemText(){var p=wrap.querySelector('.status.problem');return p?p.textContent.replace(/^Updated [^.]*\\.\\s*/,''):'';}
function refreshBoard(focus,opts){var f=focus||focusTarget(),was=problemText(),o=opts||{};
  return fetch('/board?token='+encodeURIComponent(TOKEN)).then(function(r){
    if(!r.ok)throw new Error(GONE);return r.text();})
  .then(function(h){wrap.innerHTML=h;bindBoard();if(o.glide)glide(o.glide,o.skip);restoreFocus(f);
    var p=problemText();if(p&&p!==was)document.getElementById('announce').textContent=wrap.querySelector('.status').textContent;});
}
/* the row after this one in its column or bin (focus moves there when this one leaves); if it was the last there, the
   nearest one anywhere on the page, so focus is never dropped */
function neighbour(li){var box=li.closest('.band,.bin');if(!box)return null;
  var all=[].slice.call(box.querySelectorAll('.row[data-id]')),i=all.indexOf(li),n=all[i+1]||all[i-1];
  if(!n){all=listRows();i=all.indexOf(li);n=all[i+1]||all[i-1];}
  return n?n.dataset.id:null;}

/* --- motion ------------------------------------------------------------------
   A ticked item lifts off the glass as a small card and arcs into Completed while the list closes up under it;
   Undo (or unticking it in Completed) flies it home. Ticking off the last thing due today brings one bird flying in
   to land on the empty branch in Now, chirping if sounds are on. With reduced motion none of this moves: the toast and the list
   itself still say what happened. */
var CALM=matchMedia('(prefers-reduced-motion: reduce)'),SETTLE='cubic-bezier(.16,1,.3,1)';
function rectOf(el){return el.getBoundingClientRect();}
function inView(r){return r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth;}
function todayLeft(){var m=document.getElementById('board-meta');return m?(+m.dataset.todayLeft||0):0;}
/* a copy of the row that can travel while the list is rebuilt underneath it */
function ghost(li){var r=rectOf(li),card=li.cloneNode(true),f=document.createElement('div');
  card.classList.remove('leaving','lifted');card.removeAttribute('data-id');
  card.querySelectorAll('[id]').forEach(function(x){x.removeAttribute('id');});
  f.className='fly';f.setAttribute('aria-hidden','true');f.inert=true;
  f.style.cssText='left:'+r.left+'px;top:'+r.top+'px;width:'+r.width+'px';
  f.appendChild(card);document.body.appendChild(f);return {f:f,card:card,r:r};}
function lift(g){return g.card.animate([{transform:'scale(1)',backgroundColor:'rgba(0,0,0,0)',boxShadow:'0 0 0 0 rgba(0,0,0,0)'},
  {transform:'scale(1.03)'}],{duration:160,easing:SETTLE,fill:'forwards'}).finished;}
/* where an item goes into Completed: the item itself if the bin is open and in view, else the bin's heading,
   else the window's edge in the bin's direction */
function binSpot(id,kind){var bin=wrap.querySelector('.bin.'+(kind||'completed'));if(!bin)return null;
  var row=bin.open&&id?bin.querySelector('.row[data-id="'+CSS.escape(id)+'"]'):null,r=row&&rectOf(row);
  if(r&&inView(r))return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,row:row,on:true};
  r=rectOf(bin.querySelector('.bin-title'));
  if(inView(r))return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,on:true};
  return {x:r.left+Math.min(r.width,120)/2,y:r.top<0?-40:innerHeight+40,w:120,on:false};}
/* carry the ghost's centre from a to b (offsets from where it started) on a thrown arc: up a little, then down */
/* Into Completed it's a toss: up a little, then down. Coming home it's a glide: it rises fast and eases sideways into
   its slot, arriving softly with nothing to overshoot. The animations are kept on the ghost so Undo can stop them. */
function arc(g,a,b,home){var dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy),
    ms=Math.round(home?Math.max(420,Math.min(640,320+d*.35)):Math.max(460,Math.min(760,360+d*.4))),
    peak=Math.min(a.y,b.y)-Math.min(44,16+d*.05);
  var x=g.f.animate([{transform:'translateX('+a.x+'px)',opacity:a.o},{opacity:1,offset:.15},{opacity:1,offset:.8},
    {transform:'translateX('+b.x+'px)',opacity:b.o}],{duration:ms,easing:home?'cubic-bezier(.4,0,.2,1)':'cubic-bezier(.45,0,.3,1)',fill:'forwards'});
  var y=g.card.animate(home?[{transform:'translateY('+a.y+'px) scale('+a.s+')'},{transform:'translateY('+b.y+'px) scale('+b.s+')'}]:[
    {transform:'translateY('+a.y+'px) scale('+a.s+')',easing:'cubic-bezier(.25,.6,.4,1)'},
    {transform:'translateY('+peak+'px) scale('+((a.s+b.s)/2)+') rotate('+(dx<0?2:-2)+'deg)',offset:.3,easing:'cubic-bezier(.55,0,.85,.4)'},
    {transform:'translateY('+b.y+'px) scale('+b.s+')'}],{duration:ms,easing:home?SETTLE:'linear',fill:'forwards'});
  g.anims=[x,y];return y.finished;}
/* stop a ghost where it is and take it away (Undo turning a flight around) */
function halt(g){(g.anims||[]).forEach(function(a){a.cancel();});g.f.remove();}
/* the card sinks back into the glass where it lands */
function settle(g){return g.card.animate([{backgroundColor:'rgba(0,0,0,0)',boxShadow:'0 0 0 0 rgba(0,0,0,0)'}],
  {duration:140,easing:'ease-out',fill:'forwards'}).finished;}
function pulseBin(kind){var s=wrap.querySelector('.bin.'+(kind||'completed')+' summary');
  if(s&&inView(rectOf(s))){s.classList.remove('pulse');void s.offsetWidth;s.classList.add('pulse');}}
var flying={};   /* id -> its card still on the way to a bin */
function toBin(g,id,kind){var to=binSpot(id,kind);if(!to){g.f.remove();return Promise.resolve();}
  var r=g.r,cx=r.left+r.width/2,cy=r.top+r.height/2,s=to.row?to.w/r.width:Math.max(.28,Math.min(.6,to.w/r.width));
  if(to.row)to.row.classList.add('lifted');
  flying[id]=g;
  return arc(g,{x:0,y:0,s:1.03,o:1},{x:to.x-cx,y:to.y-cy,s:s,o:to.on&&!to.row?0:1})
    .then(function(){return to.row?settle(g):null;})
    .then(function(){delete flying[id];if(to.row)to.row.classList.remove('lifted');g.f.remove();pulseBin(kind);});}
/* where a put-back item starts from: its own row in an open bin, or the bin's heading */
function fromSpot(li,kind){if(li){var r=rectOf(li);if(inView(r))return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,row:true,on:true};}
  return binSpot(null,kind);}
function home(id,from){if(!from||CALM.matches)return;
  var row=wrap.querySelector('.bands .row[data-id="'+CSS.escape(id)+'"]');if(!row)return;
  var r=rectOf(row);if(!inView(r))return;
  var g=ghost(row),cx=r.left+r.width/2,cy=r.top+r.height/2;row.classList.add('lifted');
  arc(g,{x:from.x-cx,y:from.y-cy,s:from.row?from.w/r.width:.4,o:from.row?1:0},{x:0,y:0,s:1,o:1},true)
    .then(function(){return settle(g);}).then(function(){row.classList.remove('lifted');g.f.remove();},function(){});}
/* FLIP: remember where things were, rebuild, then let them glide from there to their new places.
   (The bins don't glide: a flying item aims at where Completed is, and it must already be there.) */
var GLIDE='.bands .row[data-id],.bands .grp,.bands .dayclear,.bands .clear,.bands .empty';
function keyOf(el){if(el.dataset.id)return 'r'+el.dataset.id;
  var b=el.closest('.band');return (b?b.getAttribute('aria-labelledby'):'')+'|'+el.className+'|'+(el.classList.contains('grp')?el.textContent:'');}
function layout(){var m={};wrap.querySelectorAll(GLIDE).forEach(function(el){m[keyOf(el)]=rectOf(el).top;});return m;}
function glide(before,skip){wrap.querySelectorAll(GLIDE).forEach(function(el){if(skip&&el.dataset.id===skip)return;
  var k=keyOf(el);
  if(k in before){var dy=before[k]-rectOf(el).top;
    if(Math.abs(dy)>1)el.animate([{transform:'translateY('+dy+'px)'},{transform:'none'}],{duration:380,easing:SETTLE});}
  else el.animate([{opacity:0},{opacity:1}],{duration:260,delay:140,easing:'ease-out',fill:'backwards'});});}
/* The bins open and close in place: a bin grows down out of its heading to show its items, or folds back up into
   it. Each keeps its own column, so nothing else on the page moves; a closing bin stays open until it has folded
   away. With reduced motion they just open and close. */
wrap.addEventListener('click',function(ev){
  var sum=ev.target.closest&&ev.target.closest('.bin > summary');if(!sum||CALM.matches)return;
  var bin=sum.parentElement;ev.preventDefault();if(bin.classList.contains('moving'))return;
  var open=!bin.open,kids=[].slice.call(bin.children).filter(function(c){return c!==sum;}),from=rectOf(bin).height;
  bin.open=open;var to=rectOf(bin).height;
  if(!open)bin.open=true;
  /* an even, unhurried curve: the list unrolls rather than leaping to most of its height in the first frames */
  var dur=Math.round(Math.max(260,Math.min(520,220+Math.abs(to-from)*.35)));
  bin.classList.add('moving');if(!open)bin.classList.add('closing');
  var anims=[bin.animate([{height:from+'px'},{height:to+'px'}],{duration:dur,easing:'cubic-bezier(.4,0,.2,1)',fill:'forwards'})];
  kids.forEach(function(k){anims.push(k.animate(open?[{opacity:0,transform:'translateY(-4px)'},{opacity:1,transform:'none'}]:[{opacity:1},{opacity:0}],
    {duration:open?dur:Math.round(dur*.55),delay:open?Math.round(dur*.2):0,easing:'ease-out',fill:'both'}));});
  anims[0].finished.catch(function(){}).then(function(){
    if(!open)bin.open=false;
    anims.forEach(function(a){a.cancel();});bin.classList.remove('moving','closing');});
});
/* the last thing due today is done: one bird flies in across the window and lands on the empty branch (or, while
   tomorrow still has items, settles as the small bird beside "nothing left for today"), chirping as it lands */
var WING=DATA.wing;   /* the same small bird that marks "nothing left for today" */
function perchSpot(){var c=wrap.querySelector('.band .clear');
  if(c)return {box:c,mark:c.querySelector('.perched'),at:c.querySelector('.perched .bird'),drop:true};
  var d=wrap.querySelector('.band .dayclear');
  return d?{box:d,mark:d.querySelector('.wingmark'),at:d.querySelector('.wingmark'),drop:false}:null;}
function awaitBird(){var p=perchSpot();if(p&&!CALM.matches)p.box.classList.add('waiting');}   /* the branch stays empty until it lands */
function birdLands(){var p=perchSpot(),chirp=function(){api('/api/chirp').catch(function(){});};
  function settle(){if(p)p.box.classList.remove('waiting');chirp();}
  if(!p||CALM.matches)return settle();
  var r=rectOf(p.at);if(!inView(r))return settle();
  var x=r.left+r.width/2,y=r.top+r.height/2,dx=p.drop?14:0,dy=p.drop?-26:0,   /* it folds its wings just above the branch */
      s=Math.max(.6,r.width*.75/34),W=innerWidth,x0=W+30,y0=Math.max(24,y-300),el=document.createElement('div');
  el.className='flier';el.setAttribute('aria-hidden','true');el.innerHTML=WING;
  el.style.offsetPath="path('M"+x0+' '+y0+'C'+(W*.5)+' '+(y0-40)+' '+(x+dx+180)+' '+(y+dy-140)+' '+(x+dx)+' '+(y+dy)+"')";
  document.body.appendChild(el);
  var FLIGHT=1800;
  /* the chirp starts a second before the bird settles, so it's heard as it lands rather than after (unless Undo took
     the item back while it was in the air) */
  setTimeout(function(){if(p.mark.isConnected)chirp();},FLIGHT+(p.drop?220:0)-1000);
  el.animate([{offsetDistance:'0%',transform:'scale('+s*.5+')',opacity:0},{opacity:1,offset:.06},
    {offsetDistance:'100%',transform:'scale('+s+')',opacity:1}],{duration:FLIGHT,easing:'cubic-bezier(.25,.1,.25,1)',fill:'forwards'})
    .finished.then(function(){
      if(!p.mark.isConnected){el.remove();return;}   /* the list changed under it (Undo) */
      p.box.classList.remove('waiting');
      p.mark.animate(p.drop?[{transform:'translate('+dx+'px,'+dy+'px) rotate(-10deg)',opacity:0},
        {transform:'translate(3px,-5px) rotate(-3deg)',opacity:1,offset:.45},{transform:'none',opacity:1}]
        :[{opacity:0},{opacity:1}],{duration:p.drop?440:200,easing:'cubic-bezier(.2,.7,.3,1)'});
      return el.animate([{opacity:1},{opacity:0}],{duration:150,fill:'forwards'}).finished;})
    .then(function(){el.remove();},function(){el.remove();});}
/* Home again (Undo, or Show on list): the item comes back from wherever it is: still in the air (the flight turns
   around), its own row in an open bin, or the bin's heading. undoFor(answer), if given, is the Undo for this. */
function bringBack(id,kind,call,msg,undoFor){var from=CALM.matches?null:binSpot(id,kind),before=CALM.matches?null:layout(),answer;
  return call().then(function(r){answer=r;return refreshBoard({id:id,part:'.tick'},{glide:before,skip:id});})
    .then(function(){var g=flying[id];
      if(g&&!CALM.matches){var r=rectOf(g.card);from={x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,row:true,on:true};}
      if(g){halt(g);delete flying[id];}
      home(id,from);toast(msg,undoFor?undoFor(answer):null);})
    .catch(function(err){toast("Couldn't "+(undoFor?'save':'undo')+': '+err.message);});}
function putBack(id){bringBack(id,'completed',function(){return api('/api/done',{id:id,done:false});},'Put back on your list');}
/* Out of the list into a bin (Archive, or ticking off again after an Undo): the row lifts off as a card and arcs in
   while the list closes up under it. */
function sendAway(li,kind,call,msg,undoFor){var id=li.dataset.id,next=neighbour(li),move=!CALM.matches,g=null,up=null,
    before=move?layout():null,answer;
  if(move){g=ghost(li);li.classList.add('lifted');up=lift(g);}else li.classList.add('leaving');
  return call().then(function(r){answer=r;return refreshBoard({id:next,part:'.tick'},{glide:before});})
    .then(function(){return up;})
    .then(function(){(g?toBin(g,id,kind):Promise.resolve(pulseBin(kind))).catch(function(){});
      toast(msg,undoFor?undoFor(answer):null);})
    .catch(function(err){if(g)g.f.remove();li.classList.remove('leaving','lifted');toast("Couldn't save: "+err.message);});}
function inList(id){return wrap.querySelector('.bands .row[data-id="'+CSS.escape(id)+'"]');}
/* Undo for putting something back from Completed: tick it off again */
function tickAgain(id){var row=inList(id),call=function(){return api('/api/done',{id:id,done:true});};
  if(row)sendAway(row,'completed',call,'Moved to Completed');
  else call().then(function(){return refreshBoard();}).then(function(){toast('Moved to Completed');}).catch(function(e){toast("Couldn't undo: "+e.message);});}
/* the item's title as it reads, without the screen-reader note on links */
function titleOf(li){var t=li.querySelector('.t').cloneNode(true);t.querySelectorAll('.sr').forEach(function(x){x.remove();});return t.textContent.trim();}
var toastTimer;
var undoFn=null;
function toast(msg,undo){var t=document.getElementById('toast'),s=document.createElement('span');
  t.textContent='';s.textContent=msg;t.appendChild(s);undoFn=undo||null;
  if(undo){var b=document.createElement('button');b.type='button';b.className='toast-undo';b.textContent='Undo';b.title='Undo (Ctrl+Z)';
    b.addEventListener('click',runUndo);t.appendChild(b);}
  t.classList.toggle('has-action',!!undo);t.classList.add('show');clearTimeout(toastTimer);
  toastTimer=setTimeout(function(){t.classList.remove('show');undoFn=null;},undo?6000:2800);}
function runUndo(){var f=undoFn,t=document.getElementById('toast'),b=t.querySelector('.toast-undo');undoFn=null;
  if(b)b.remove();t.classList.remove('has-action');clearTimeout(toastTimer);if(f)f();}   /* stays up; the next words replace these */
document.addEventListener('keydown',function(ev){var a=document.activeElement||{},   /* leave Ctrl+Z to text fields */
    typing=a.tagName==='TEXTAREA'||a.isContentEditable||(a.tagName==='INPUT'&&!/^(checkbox|radio|button|submit|color|range)$/.test(a.type));
  if(undoFn&&(ev.ctrlKey||ev.metaKey)&&!ev.shiftKey&&(ev.key==='z'||ev.key==='Z')&&!typing){ev.preventDefault();runUndo();}});
/* Preferences are saved by Birdbrain; course edits are batched while you type. */
var pendingCourses={},courseTimer;
function savePrefs(patch){if(!LIVE)return;api('/api/prefs',patch).catch(function(e){toast("Couldn't save: "+e.message);});}
function saveCourse(code){pendingCourses[code]=PREFS.courses[code]||null;clearTimeout(courseTimer);
  courseTimer=setTimeout(function(){var p=pendingCourses;pendingCourses={};savePrefs({courses:p});},400);}

/* --- the board (re-bound after every refresh) ----------------------------- */
function bindBoard(){
  document.querySelectorAll('.row[data-id] .tick').forEach(function(box){
    var li=box.closest('.row');
    if(!LIVE){box.disabled=true;box.title='Open the list from the Birdbrain icon to tick items off';return;}
    box.addEventListener('change',function(){
      var done=box.checked,id=li.dataset.id,next=neighbour(li),left=todayLeft(),move=!CALM.matches,g=null,up=null,
          from=!done&&move?fromSpot(li):null,before=move?layout():null;
      if(done&&move){g=ghost(li);li.classList.add('lifted');up=lift(g);}   /* it lifts while Birdbrain saves */
      else if(!move)li.classList.add('leaving');
      api('/api/done',{id:id,done:done})
        .then(function(){return refreshBoard(done?{id:next,part:'.tick'}:{id:id,part:'.tick'},{glide:before,skip:done?null:id});})
        .then(function(){return up;})
        .then(function(){
          if(done){var clear=left>0&&todayLeft()===0;
            if(clear)awaitBird();
            (g?toBin(g,id):Promise.resolve(pulseBin())).then(function(){if(clear)birdLands();},function(){});   /* stopped by Undo */
            toast(clear?'Moved to Completed. Nothing else is due today.':'Moved to Completed',function(){putBack(id);});}
          else{home(id,from);toast('Put back on your list',function(){tickAgain(id);});}
        }).catch(function(err){if(g)g.f.remove();box.checked=!done;li.classList.remove('leaving','lifted');toast("Couldn't save: "+err.message);});
    });
  });
  document.querySelectorAll('.act.more').forEach(function(btn){btn.addEventListener('click',function(){
    var open=btn.getAttribute('aria-expanded')!=='true';btn.setAttribute('aria-expanded',open);
    btn.textContent=open?'Hide details':'Details';
    document.getElementById(btn.getAttribute('aria-controls')).hidden=!open;});});
  document.querySelectorAll('.act.edit').forEach(function(btn){btn.addEventListener('click',function(){
    var li=btn.closest('.row');openItemForm(JSON.parse(li.dataset.manual),li.dataset.id);});});
  document.querySelectorAll('.act.del').forEach(function(btn){btn.addEventListener('click',function(){
    if(!btn.dataset.armed){btn.dataset.armed='1';btn.textContent='Click again to delete';
      setTimeout(function(){delete btn.dataset.armed;btn.textContent='Delete';},4000);return;}
    var li=btn.closest('.row'),name=titleOf(li);
    api('/api/items/delete',{id:li.dataset.id}).then(function(r){return refreshBoard({id:neighbour(li),part:'.tick'}).then(function(){
      toast('Deleted “'+name+'”',function(){api('/api/items/restore',r.item)
        .then(function(){return refreshBoard({id:r.item.id,part:'.tick'});}).then(function(){toast('Put back “'+name+'”');})
        .catch(function(err){toast("Couldn't undo: "+err.message);});});});})
      .catch(function(err){toast(err.message);});});});
  /* Archive: any item, out of the way until you want it; it waits in Archived */
  document.querySelectorAll('.act.arch').forEach(function(btn){btn.addEventListener('click',function(){
    var li=btn.closest('.row'),id=li.dataset.id;
    sendAway(li,'archived',function(){return api('/api/place',{id:id,how:'archived'});},'Moved to Archived',
      function(r){return function(){bringBack(id,'archived',function(){return api('/api/place',{id:id,how:r.was});},'Back on your list');};});});});
  /* Show on list: anything in Archived, whether you archived it or a keyword or duplicate did */
  document.querySelectorAll('.act.show').forEach(function(btn){btn.addEventListener('click',function(){
    var id=btn.closest('.row').dataset.id;
    bringBack(id,'archived',function(){return api('/api/place',{id:id,how:'shown'});},'Back on your list',
      function(r){return function(){var row=inList(id),call=function(){return api('/api/place',{id:id,how:r.was});};
        if(row)sendAway(row,'archived',call,'Moved to Archived');
        else call().then(function(){return refreshBoard();}).then(function(){toast('Moved to Archived');}).catch(function(e){toast("Couldn't undo: "+e.message);});};});});});
  document.querySelectorAll('.bin[data-bin]').forEach(function(d){
    /* Browsers also fire "toggle" for a bin that is built already open; only save real changes,
       or saving would bump the version and refresh the page in a loop. */
    d.addEventListener('toggle',function(){if(!!PREFS.bins[d.dataset.bin]===d.open)return;
      PREFS.bins[d.dataset.bin]=d.open;var b={};b[d.dataset.bin]=d.open;savePrefs({bins:b});});});
  var gear=document.getElementById('open-settings');
  if(gear)gear.addEventListener('click',function(){openSettings();});
  var add=document.getElementById('open-add');
  if(add)add.addEventListener('click',function(){openItemForm(null,null);});
}

/* --- dialogs ------------------------------------------------------------ */
var settings=document.getElementById('settings'),itemDlg=document.getElementById('add-item'),itemForm=document.getElementById('add-form');
/* Settings opens on the tab you last used, or on the one asked for (and a part of it, such as the shortcut list) */
function openSettings(tab,part){syncCourseInputs();settings.showModal();
  var t=tab&&setTabs.filter(function(x){return x.id==='tab-'+tab;})[0];
  if(t)showTab(t);else t=settings.querySelector('[role=tab][aria-selected=true]');
  var p=part&&document.getElementById(part);if(p&&!p.closest('[hidden]'))p.scrollIntoView({block:'start'});
  if(t)t.focus();}
function scanNow(){api('/api/scan').then(function(){toast('Scanning now. Your list updates when it\u2019s done.');})
  .catch(function(e){toast("Couldn't start a scan: "+e.message);});}
/* Single-key shortcuts (N, S, R, ?): only while no window is open and you aren't typing, and never with Ctrl or Alt */
var SHORTCUTS={n:function(){if(LIVE)openItemForm(null,null);},s:function(){openSettings();},
  r:function(){if(LIVE)scanNow();},j:function(){focusRow(listRows()[0]);},'?':function(){openSettings('app','keys-sec');}};
/* On an item: ↓/J and ↑/K to the next and previous item (through the columns, then any open bin), ←/→ to the first item
   of the column beside, O (or Enter on its tick box) opens it, A archives it or shows it again, E edits one you added. */
function listRows(){return [].slice.call(wrap.querySelectorAll('.row[data-id]')).filter(function(r){return r.offsetParent!==null;});}
function focusRow(r){if(!r)return;(r.querySelector('.tick')||r).focus();}
wrap.addEventListener('keydown',function(ev){
  if(ev.ctrlKey||ev.metaKey||ev.altKey||ev.defaultPrevented)return;
  var row=ev.target.closest&&ev.target.closest('.row[data-id]'),k=ev.key;
  if(!row||(ev.target.tagName==='INPUT'&&ev.target.type!=='checkbox'))return;
  var all=listRows(),i=all.indexOf(row),go=null,act=function(sel){var b=row.querySelector(sel);if(b&&LIVE){ev.preventDefault();b.click();}};
  if(k==='ArrowDown'||k==='j'||k==='J')go=all[i+1];
  else if(k==='ArrowUp'||k==='k'||k==='K')go=all[i-1];
  else if(k==='ArrowRight'||k==='ArrowLeft'){
    var boxes=[].slice.call(wrap.querySelectorAll('.band,.bin[open]')),b=boxes.indexOf(row.closest('.band,.bin')),step=k==='ArrowRight'?1:-1;
    for(var j=b+step;j>=0&&j<boxes.length&&!go;j+=step)go=boxes[j].querySelector('.row[data-id]');}
  else if(k==='o'||k==='O'||(k==='Enter'&&ev.target.classList.contains('tick'))){var a=row.querySelector('a.t');if(a){ev.preventDefault();a.click();}return;}
  else if(k==='a'||k==='A')return act('.act.arch,.act.show');
  else if(k==='e'||k==='E')return act('.act.edit');
  else return;
  ev.preventDefault();if(go)focusRow(go);});
document.addEventListener('keydown',function(ev){
  if(ev.ctrlKey||ev.metaKey||ev.altKey||ev.defaultPrevented||ev.repeat||document.querySelector('dialog[open]'))return;
  var a=document.activeElement||{};
  if(a.tagName==='TEXTAREA'||a.tagName==='SELECT'||a.isContentEditable||(a.tagName==='INPUT'&&!/^(checkbox|radio|button|submit)$/.test(a.type)))return;
  var f=SHORTCUTS[ev.key.length===1?ev.key.toLowerCase():''];
  if(f){ev.preventDefault();f();}});
/* A sheet leaves the way it came: a quick fade and drop, the dimmed page brightening with it. */
function closeSheet(d){if(!d.open||d.classList.contains('closing'))return;
  if(CALM.matches){d.close();return;}
  var done=function(){if(!d.classList.contains('closing'))return;d.classList.remove('closing');d.close();};
  d.classList.add('closing');
  d.addEventListener('animationend',function h(ev){if(ev.target!==d)return;d.removeEventListener('animationend',h);done();});
  setTimeout(done,400);}   /* in case the animation never runs */
[settings,itemDlg].forEach(function(d){
  d.addEventListener('click',function(ev){if(ev.target===d)closeSheet(d);});
  d.addEventListener('cancel',function(ev){ev.preventDefault();closeSheet(d);});   /* Esc */
  d.querySelectorAll('[data-close]').forEach(function(b){b.addEventListener('click',function(){closeSheet(d);});});
});

/* Settings tabs: one pane at a time. Arrow keys, Home and End move along the tabs (the ARIA tabs pattern),
   and the dialog reopens on the tab you last used. */
var setTabs=[].slice.call(settings.querySelectorAll('[role=tab]')).filter(function(t){return getComputedStyle(t).display!=='none';});
function showTab(t,focus){setTabs.forEach(function(x){var on=x===t;x.setAttribute('aria-selected',on?'true':'false');x.tabIndex=on?0:-1;
  document.getElementById(x.getAttribute('aria-controls')).hidden=!on;});if(focus)t.focus();}
setTabs.forEach(function(t,i){t.addEventListener('click',function(){showTab(t);});
  t.addEventListener('keydown',function(ev){var j={ArrowRight:i+1,ArrowLeft:i-1,Home:0,End:setTabs.length-1}[ev.key];
    if(j===undefined)return;ev.preventDefault();showTab(setTabs[(j+setTabs.length)%setTabs.length],true);});});

/* add / edit your own items (one form; editing just fills it in first) */
var editing=null,editFields=null;
function openItemForm(fields,id){
  var f=itemForm.elements;editing=id;editFields=fields;
  itemForm.querySelector('.form-error').textContent='';
  document.getElementById('add-title').textContent=id?'Edit item':'Add item';
  itemForm.querySelector('button[type=submit]').textContent=id?'Save changes':'Add item';
  if(fields){f.title.value=fields.title;f.kind.value=fields.kind;f.date.value=fields.date;f.time.value=fields.time;
    f.course.value=fields.course;f.notes.value=fields.notes;}
  else if(itemForm.dataset.lastMode==='edit'){itemForm.reset();}
  itemForm.dataset.lastMode=id?'edit':'add';
  itemDlg.showModal();f.title.focus();
}
itemForm.addEventListener('submit',function(ev){
  ev.preventDefault();
  var f=itemForm.elements,err=itemForm.querySelector('.form-error'),data={title:f.title.value.trim(),kind:f.kind.value,
    date:f.date.value,time:f.time.value,course:f.course.value.trim(),notes:f.notes.value.trim()};
  if(!data.title){err.textContent='Give the item a title.';f.title.focus();return;}
  if(!data.date){err.textContent='Pick a due date.';f.date.focus();return;}
  if(editing)data.id=editing;
  err.textContent='';var go=itemForm.querySelector('button[type=submit]');go.disabled=true;
  var was=editing,before=editFields;
  api(editing?'/api/items/update':'/api/items',data).then(function(r){return refreshBoard({id:r.id,part:'.tick'}).then(function(){
    closeSheet(itemDlg);
    if(was)toast('Saved “'+data.title+'”',function(){api('/api/items/update',Object.assign({},before,{id:was}))
      .then(function(){return refreshBoard();}).then(function(){toast('Changes undone');})
      .catch(function(e){toast("Couldn't undo: "+e.message);});});
    else{toast('Added “'+data.title+'”',function(){api('/api/items/delete',{id:r.id})
      .then(function(){return refreshBoard();}).then(function(){toast('Removed “'+data.title+'”');})
      .catch(function(e){toast("Couldn't undo: "+e.message);});});
      f.title.value='';f.time.value='';f.notes.value='';}
  });}).catch(function(e){err.textContent=e.message;}).then(function(){go.disabled=false;});
});

/* theme + mode: each layout keeps its own theme (PREFS.theme for Glass, PREFS.focus_theme for Focus) */
var media=matchMedia('(prefers-color-scheme: light)'),THEME_KEY=PREFS.layout==='glass'?'theme':'focus_theme';
var customPanel=document.getElementById('custom-panel'),customCss=document.getElementById('custom-css'),customTimer;
function applyTheme(){
  root.classList.add('no-anim');   /* switch colours instantly, not via hover transitions */
  root.dataset.theme=PREFS[THEME_KEY];root.dataset.modePref=PREFS.mode;
  root.dataset.mode=PREFS.mode==='system'?(media.matches?'light':'dark'):PREFS.mode;syncCourseInputs();syncLook();
  requestAnimationFrame(function(){requestAnimationFrame(function(){root.classList.remove('no-anim');});});}
media.addEventListener('change',function(){if(PREFS.mode==='system')applyTheme();});
/* each theme's day (light) and night (dark) halves are the choices */
var followSys=document.getElementById('follow-system');
function syncLook(){settings.querySelectorAll('input[name=look]').forEach(function(r){
  r.checked=r.value===PREFS[THEME_KEY]+':'+root.dataset.mode;});followSys.checked=PREFS.mode==='system';
  if(customPanel)customPanel.hidden=PREFS[THEME_KEY]!=='custom';}
settings.querySelectorAll('input[name=look]').forEach(function(r){r.addEventListener('change',function(){
  var v=r.value.split(':'),patch={mode:v[1]};PREFS[THEME_KEY]=v[0];PREFS.mode=v[1];patch[THEME_KEY]=v[0];
  applyTheme();savePrefs(patch);});});
/* The Custom theme: its CSS sits in <style id="custom-css">, and Birdbrain sends a fresh one after each change,
   with the thumbnails and any colours that won't read. */
function customApplied(r){PREFS.glass_custom=r.prefs.glass_custom;PREFS.focus_custom=r.prefs.focus_custom;customCss.textContent=r.css;
  ['light','dark'].forEach(function(m){var url=r.thumbs&&r.thumbs[m];
    settings.querySelectorAll('.theme-opt[data-theme=custom] .half.photo[data-slot='+m+'],#custom-panel .slot[data-slot='+m+'] .slot-pic')
      .forEach(function(el){el.style.backgroundImage=url?'url("'+url+'")':'';el.classList.toggle('no-photo',!url);});
    var rm=settings.querySelector('#custom-panel .slot[data-slot='+m+'] .slot-remove');if(rm)rm.hidden=!url;});
  settings.querySelectorAll('.custom-mode').forEach(function(fs){fs.querySelector('.warn').textContent=((r.warnings||{})[fs.dataset.mode]||[]).join(' ');});}
function saveCustom(patch){clearTimeout(customTimer);customTimer=setTimeout(function(){
  api('/api/prefs',patch).then(customApplied).catch(function(e){toast("Couldn't save: "+e.message);});},150);}
if(customPanel&&customPanel.dataset.kind==='focus'){   /* four colours for day and four for night */
  customPanel.querySelectorAll('input[type=color]').forEach(function(inp){inp.addEventListener('input',function(){
    var fc={light:{},dark:{}};customPanel.querySelectorAll('input[type=color]').forEach(function(i){fc[i.dataset.mode][i.dataset.role]=i.value;});
    var m=inp.dataset.mode,c=fc[m],half=settings.querySelector('.theme-opt[data-theme=custom] .half[data-slot='+m+']');
    if(half){half.style.background=c.bg;half.querySelector('.tone-word').style.color=c.struct;
      half.querySelector('.tone-ink').style.background=c.text;half.querySelector('.tone-dot').style.background=c.accent;}
    saveCustom({focus_custom:fc});});});}
if(customPanel&&customPanel.dataset.kind==='glass'){   /* your own photos, and an accent */
  var customMsg=document.getElementById('custom-msg'),glassAccent=document.getElementById('glass-accent');
  glassAccent.addEventListener('input',function(){saveCustom({glass_accent:glassAccent.value});});
  customPanel.querySelectorAll('.slot').forEach(function(slot){
    var m=slot.dataset.slot,word=m==='light'?'Day':'Night',file=slot.querySelector('input[type=file]');
    file.addEventListener('change',function(){var pic=file.files[0];file.value='';if(!pic)return;
      if(['image/jpeg','image/png','image/webp'].indexOf(pic.type)<0){customMsg.textContent='Choose a JPEG, PNG or WebP picture.';return;}
      if(pic.size>25*1024*1024){customMsg.textContent='That picture is over 25 MB. Choose a smaller one.';return;}
      customMsg.textContent='Measuring your picture…';
      fetch('/api/photo?slot='+m,{method:'POST',headers:{'Content-Type':pic.type,'X-Birdbrain-Token':TOKEN},body:pic})
        .then(function(res){return res.json().catch(function(){return {};}).then(function(j){
          if(res.status===403)throw new Error(GONE);if(!res.ok)throw new Error(j.error||('Error '+res.status));return j;});})
        .then(function(r){customApplied(r);PREFS.theme='custom';var patch={theme:'custom'};
          if(PREFS.mode!=='system'){PREFS.mode=m;patch.mode=m;}applyTheme();savePrefs(patch);
          customMsg.textContent=word+' photo saved. The glass over it is tinted '+Math.round(r.alpha*100)+'%, so every word stays readable.';})
        .catch(function(e){customMsg.textContent="Couldn't use that picture: "+e.message;});});
    slot.querySelector('.slot-remove').addEventListener('click',function(){
      api('/api/photo-remove',{slot:m}).then(function(r){customApplied(r);customMsg.textContent=word+' photo removed.';})
        .catch(function(e){customMsg.textContent="Couldn't remove it: "+e.message;});});});}
followSys.addEventListener('change',function(){PREFS.mode=followSys.checked?'system':root.dataset.mode;
  applyTheme();savePrefs({mode:PREFS.mode});});
syncLook();
/* Each layout has its own stylesheet, so switching layout saves and reloads the page. */
settings.querySelectorAll('input[name=layout]').forEach(function(r){
  r.checked=r.value===PREFS.layout;
  r.addEventListener('change',function(){if(!LIVE){toast('Open the list from the Birdbrain icon to change the layout');return;}
    api('/api/prefs',{layout:r.value}).then(function(){switchLayout(r.value);}).catch(function(e){toast("Couldn't save: "+e.message);});});});
/* Each layout has its own stylesheet, so the page reloads; it crossfades through the new layout's own ground colour.
   The list sinks away under a veil of that colour, the page reloads beneath it, and the veil lifts off the new look
   (the arriving class, set before the first paint). The window's own title bar stays put throughout. */
function switchLayout(to){var ground=((DATA.grounds||{})[to]||{})[root.dataset.mode]||'';
  try{sessionStorage.setItem('bb-arrive',ground);}catch(e){}
  if(CALM.matches){location.reload();return;}
  closeSheet(settings);
  var veil=document.createElement('div');veil.className='veil';veil.style.background=ground;document.body.appendChild(veil);
  wrap.animate([{opacity:1,transform:'none'},{opacity:0,transform:'translateY(10px) scale(.99)'}],
    {duration:260,easing:'cubic-bezier(.4,0,1,1)',fill:'forwards'});
  veil.animate([{opacity:0},{opacity:1}],{duration:320,delay:80,easing:'cubic-bezier(.4,0,.6,1)',fill:'forwards'})
    .finished.then(function(){location.reload();},function(){location.reload();});}
if(root.classList.contains('arriving'))setTimeout(function(){root.classList.remove('arriving');root.style.removeProperty('--arrive');},1000);
/* frame width (glass layout) */
settings.querySelectorAll('input[name=frame]').forEach(function(r){
  r.checked=r.value===(PREFS.frame||'wide');
  r.addEventListener('change',function(){PREFS.frame=r.value;root.dataset.frame=r.value;savePrefs({frame:r.value});});});

/* the call when something new is due */
var soundOn=document.getElementById('sound-on');soundOn.checked=PREFS.sound!==false;
soundOn.addEventListener('change',function(){PREFS.sound=soundOn.checked;savePrefs({sound:soundOn.checked});});
document.getElementById('sound-test').addEventListener('click',function(){api('/api/sound').catch(function(e){toast(e.message);});});

/* the tray menu's actions: scan, sign in, hidden keywords, files, quit */
var nowMsg=document.getElementById('scan-now-msg');
function follow(el){var seen=false,tries=0,iv=setInterval(function(){status().then(function(s){
  if(s.scanning){seen=true;el.textContent=s.status;}
  if((seen&&!s.scanning)||(!seen&&++tries>5)){clearInterval(iv);el.textContent=s.status;refreshBoard();}
}).catch(function(){clearInterval(iv);});},2000);}
function startScan(full){api('/api/scan',full?{full:true}:{}).then(function(){
  nowMsg.textContent=full?'Full Moodle scan starting. This can take a few minutes.':'Scan starting…';follow(nowMsg);})
  .catch(function(e){nowMsg.textContent=e.message;});}
document.getElementById('scan-now').addEventListener('click',function(){startScan(false);});
document.getElementById('scan-full').addEventListener('click',function(){startScan(true);});
/* where Moodle and Outlook are: fix a mistyped address or move to another. A new one is signed in to straight away. */
var addrForm=document.getElementById('addr-form'),addrMoodle=document.getElementById('addr-moodle'),
    addrOutlook=document.getElementById('addr-outlook'),addrErr=document.getElementById('addr-error'),addrMsg=document.getElementById('addr-msg'),
    OUTLOOK_SITES={school:'https://outlook.office.com',personal:'https://outlook.live.com'};
function addrAccount(){return addrForm.querySelector('input[name=addr-account]:checked').value;}
addrForm.querySelectorAll('input[name=addr-account]').forEach(function(r){r.addEventListener('change',function(){
  var now=addrOutlook.value.trim();document.getElementById('addr-outlook-field').hidden=r.value==='none';
  if(OUTLOOK_SITES[r.value]&&(!now||now===OUTLOOK_SITES.school||now===OUTLOOK_SITES.personal))addrOutlook.value=OUTLOOK_SITES[r.value];});});
addrForm.addEventListener('submit',function(ev){ev.preventDefault();addrErr.textContent='';addrMsg.textContent='';
  var none=addrAccount()==='none',btn=addrForm.querySelector('button[type=submit]');
  [addrMoodle,addrOutlook].forEach(function(i){i.removeAttribute('aria-invalid');i.removeAttribute('aria-describedby');});
  btn.disabled=true;
  api('/api/addresses',{moodle:addrMoodle.value.trim(),outlook:addrOutlook.value.trim(),no_outlook:none}).then(function(r){
    addrMoodle.value=r.moodle;if(r.outlook)addrOutlook.value=r.outlook;
    addrMsg.textContent=r.sign_in?"Saved. The sign-in window is opening for the new address. It closes by itself once you're signed in."
      :r.outlook_off?'Saved. Birdbrain stops reading Outlook; what it already found stays on your list.'
      :'Saved. These are the addresses Birdbrain was already using.';})
  .catch(function(e){addrErr.textContent=e.message;   /* the message names the site it's about */
    var bad=!none&&/outlook/i.test(e.message)?addrOutlook:addrMoodle;
    bad.setAttribute('aria-invalid','true');bad.setAttribute('aria-describedby','addr-error');bad.focus();})
  .then(function(){btn.disabled=false;});});
/* McGraw Hill Connect: how it's reached, and whether Birdbrain may renew the sign-in by itself */
var mhOpts=document.getElementById('mcgraw-options'),mhRenew=document.getElementById('mcgraw-renew'),mhAuto=document.getElementById('mcgraw-auto');
document.getElementById('site-mcgraw').addEventListener('change',function(ev){mhOpts.hidden=!ev.target.checked;});
settings.querySelectorAll('input[name=mcgraw-via]').forEach(function(r){r.addEventListener('change',function(){
  mhRenew.hidden=r.value!=='moodle';var msg=document.getElementById('sites-msg');
  api('/api/sites',{mcgraw_via:r.value}).then(function(){msg.textContent=r.value==='moodle'
    ?'Next time you sign in, click any McGraw Hill link in your Moodle course once.'
    :'Next time you sign in, sign in to Connect on its own page.';}).catch(function(e){msg.textContent="Couldn't save: "+e.message;});});});
mhAuto.addEventListener('change',function(){var msg=document.getElementById('sites-msg');
  api('/api/sites',{mcgraw_auto_renew:mhAuto.checked}).then(function(){msg.textContent=mhAuto.checked
    ?'Birdbrain will re-open your last McGraw Hill link by itself when Connect signs you out.'
    :'Birdbrain will ask you to sign in again instead.';}).catch(function(e){mhAuto.checked=!mhAuto.checked;msg.textContent="Couldn't save: "+e.message;});});
/* the other sites: saved at once; turning one on says how to sign in to it */
['gradescope','mcgraw'].forEach(function(k){var box=document.getElementById('site-'+k),msg=document.getElementById('sites-msg');
  box.addEventListener('change',function(){var b={};b[k]=box.checked;
    api('/api/sites',b).then(function(){var name=k==='gradescope'?'Gradescope':'McGraw Hill Connect';
      msg.textContent=box.checked?name+' is on. Sign in to it with “Sign in to your school sites” below, and the next scan reads it.'
        :name+' is off. Birdbrain stops reading it; what it already found stays on your list.';})
    .catch(function(e){box.checked=!box.checked;msg.textContent="Couldn't save: "+e.message;});});});
document.getElementById('sign-in').addEventListener('click',function(){api('/api/sign-in').then(function(){
  nowMsg.textContent="The sign-in window is opening. It closes by itself once you're signed in.";})
  .catch(function(e){nowMsg.textContent=e.message;});});
settings.querySelectorAll('[data-open]').forEach(function(b){b.addEventListener('click',function(){
  api('/api/open',{what:b.dataset.open}).then(function(){toast(b.dataset.open==='log'?'Opened the log':'Opened the settings file');})
  .catch(function(e){toast(e.message);});});});
var quit=document.getElementById('quit-app');
quit.addEventListener('click',function(){
  if(!quit.dataset.armed){quit.dataset.armed='1';quit.textContent='Click again to quit';
    setTimeout(function(){delete quit.dataset.armed;quit.textContent='Quit Birdbrain';},4000);return;}
  api('/api/quit').then(function(){settings.close();wrap.innerHTML='<p class="gone">Birdbrain has quit. To use it again, start Birdbrain.exe.</p>';})
    .catch(function(e){toast(e.message);});});
var KW=DATA.keywords||[],kwList=document.getElementById('kw-list'),kwForm=document.getElementById('kw-form'),
    kwInput=document.getElementById('kw-input'),kwError=document.getElementById('kw-error'),kwMsg=document.getElementById('kw-msg');
function renderKw(){kwList.textContent='';
  if(!KW.length){var none=document.createElement('li');none.className='kw-empty';none.textContent='No hidden keywords.';kwList.appendChild(none);return;}
  KW.forEach(function(k,i){var li=document.createElement('li'),w=document.createElement('span'),n=document.createElement('span'),
    rm=document.createElement('button');
    w.className='kw';w.textContent=k.keyword;n.className='kw-n';n.textContent=k.count+(k.count===1?' entry':' entries')+' hidden';
    rm.type='button';rm.className='act';rm.textContent='Remove';rm.setAttribute('aria-label','Stop hiding “'+k.keyword+'”');
    rm.addEventListener('click',function(){saveKw(KW.filter(function(_,j){return j!==i;}).map(function(x){return x.keyword;}),
      'No longer hiding “'+k.keyword+'”.');});
    li.appendChild(w);li.appendChild(n);li.appendChild(rm);kwList.appendChild(li);});}
/* what changed, said in the pane itself (a toast would sit under the open dialog), with an Undo beside it */
function kwSaid(msg,undo){kwMsg.textContent=msg;if(!undo)return;
  var b=document.createElement('button');b.type='button';b.className='act';b.textContent='Undo';
  b.addEventListener('click',function(){b.disabled=true;undo();});kwMsg.appendChild(document.createTextNode(' '));kwMsg.appendChild(b);}
function saveKw(list,msg,final){kwError.textContent='';var prev=KW.map(function(k){return k.keyword;});
  return api('/api/keywords',{keywords:list}).then(function(r){KW=r.keywords;renderKw();refreshBoard();
    kwSaid(msg,final?null:function(){saveKw(prev,'Keywords put back as they were.',true);});})
    .catch(function(e){kwError.textContent=e.message;});}
kwForm.addEventListener('submit',function(ev){ev.preventDefault();var v=kwInput.value.split(' ').filter(Boolean).join(' ').trim();
  if(!v){kwError.textContent='Type a word to hide.';kwInput.focus();return;}
  if(KW.some(function(k){return k.keyword.toLowerCase()===v.toLowerCase();})){kwError.textContent='“'+v+'” is already hidden.';return;}
  saveKw(KW.map(function(k){return k.keyword;}).concat([v]),'Hiding entries with “'+v+'”.').then(function(){kwInput.value='';});});
renderKw();

/* inbox scan back to a date */
var scanGo=document.getElementById('scan-go'),scanMsg=document.getElementById('scan-msg'),scanStop=document.getElementById('scan-stop');
function scanDone(){scanGo.disabled=false;scanStop.hidden=true;scanStop.disabled=false;}
function watchScan(){scanStop.hidden=false;var iv=setInterval(function(){status().then(function(s){scanMsg.textContent=s.status;
  if(!s.inbox){clearInterval(iv);scanDone();refreshBoard();}}).catch(function(){clearInterval(iv);scanDone();});},2000);}
/* Stop: a queued scan never starts; a running one ends where it is, and what it already found stays */
scanStop.addEventListener('click',function(){scanStop.disabled=true;
  api('/api/scan-stop').then(function(){scanMsg.textContent='Stopping. Anything it has already found stays on your list.';})
    .catch(function(e){scanMsg.textContent=e.message;scanStop.disabled=false;});});
scanGo.addEventListener('click',function(){
  var since=document.getElementById('scan-since').value;
  if(!since){scanMsg.textContent='Pick a date first.';return;}
  scanGo.disabled=true;scanMsg.textContent='Starting…';
  api('/api/scan-mail',{since:since}).then(watchScan).catch(function(e){scanMsg.textContent=e.message;scanGo.disabled=false;});
});

/* course colours & nicknames (the page is built with saved ones; this applies edits live) */
function applyCourses(){
  document.querySelectorAll('.code[data-code]').forEach(function(el){
    var c=PREFS.courses[el.dataset.code]||{};
    el.textContent=c.nick||el.dataset.code;el.title=c.nick?el.dataset.code:'';
    el.style.removeProperty('color');if(c.color)el.style.setProperty('--cc',c.color);else el.style.removeProperty('--cc');});
}
function hex(v){v=(v||'').trim().toLowerCase();return /^#[0-9a-f]{6}$/.test(v)?v:'#888888';}
function effective(code){
  var c=PREFS.courses[code];if(c&&c.color)return c.color.toLowerCase();
  return hex(getComputedStyle(root).getPropertyValue('--struct'));
}
function lum(h){var c=[1,3,5].map(function(i){var x=parseInt(h.substr(i,2),16)/255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4);});return .2126*c[0]+.7152*c[1]+.0722*c[2];}
function ratio(a,b){var x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
function syncCourseInputs(){
  var bg=hex(getComputedStyle(root).getPropertyValue('--bg')),codes=[];
  settings.querySelectorAll('.courses li').forEach(function(li){codes.push(li.dataset.code);});
  settings.querySelectorAll('.courses li').forEach(function(li){
    var code=li.dataset.code,c=PREFS.courses[code]||{},col=effective(code),msgs=[];
    li.querySelector('input[type=color]').value=col;
    if(c.color)li.querySelector('.cc').style.setProperty('--cc',c.color);else li.querySelector('.cc').style.removeProperty('--cc');
    var nick=li.querySelector('.nick');if(document.activeElement!==nick)nick.value=c.nick||'';
    li.querySelector('.reset').disabled=!(c.nick||c.color);
    li.classList.toggle('unset',!c.color);   /* no dot on the list until a colour is picked; say so */
    li.querySelector('input[type=color]').title=c.color?'':'No colour yet. Pick one to mark this course.';
    var twin=c.color?codes.filter(function(o){return o!==code&&PREFS.courses[o]&&PREFS.courses[o].color&&effective(o)===col;}):[];
    if(twin.length)msgs.push('Same colour as '+twin.map(function(o){return (PREFS.courses[o]&&PREFS.courses[o].nick)||o;}).join(', ')+'.');
    li.querySelector('.warn').textContent=msgs.join(' ');
  });
}
function updateCourse(code,patch){
  var c=Object.assign({},PREFS.courses[code]||{},patch);
  Object.keys(c).forEach(function(k){if(!c[k])delete c[k];});
  if(Object.keys(c).length)PREFS.courses[code]=c;else delete PREFS.courses[code];
  applyCourses();syncCourseInputs();saveCourse(code);
}
settings.querySelectorAll('.courses li').forEach(function(li){
  var code=li.dataset.code;
  li.querySelector('input[type=color]').addEventListener('input',function(ev){updateCourse(code,{color:ev.target.value});});
  li.querySelector('.nick').addEventListener('input',function(ev){updateCourse(code,{nick:ev.target.value.trim()});});
  li.querySelector('.reset').addEventListener('click',function(){delete PREFS.courses[code];applyCourses();syncCourseInputs();saveCourse(code);});
});

bindBoard();

if(LIVE){
  /* Before the rename, preferences and ticks were kept in this browser under "studytray-…".
     Hand them to Birdbrain once, then forget them. */
  var old={};
  try{['theme','mode','courses','bins','done'].forEach(function(k){var v=localStorage.getItem('studytray-'+k);if(v!==null)old[k]=v;});}catch(e){}
  if(Object.keys(old).length&&!PREFS.imported){
    var patch={imported:true},t=old.theme,j=function(s){try{return JSON.parse(s)}catch(e){return null}};
    if(['light','night-light','paper','aubergine'].indexOf(t)>=0){patch.theme='cloudy';patch.mode='light';}
    else{if(t==='dark'||t==='night')t='cloudy';if(DATA.themes.indexOf(t)>=0)patch.theme=t;if(DATA.modes.indexOf(old.mode)>=0)patch.mode=old.mode;}
    var cs=j(old.courses);if(cs&&typeof cs==='object')patch.courses=cs;
    var bs=j(old.bins);if(bs&&typeof bs==='object')patch.bins=bs;
    var dn=j(old.done)||{},ids=Object.keys(dn).filter(function(k){return dn[k];});
    api('/api/prefs',patch).then(function(){
      return Promise.all(ids.map(function(id){return api('/api/done',{id:id,done:true}).catch(function(){});}));
    }).then(function(){
      try{Object.keys(old).forEach(function(k){localStorage.removeItem('studytray-'+k);});}catch(e){}
      location.reload();
    }).catch(function(){});
  }
  /* Pick up new scan results without a reload, unless you're in the middle of something. */
  setInterval(function(){
    if(document.hidden||settings.open||itemDlg.open||document.querySelector('.row.leaving'))return;
    var a=document.activeElement;if(a&&wrap.contains(a)&&a.matches(':focus-visible'))return;   /* moving through the list by keyboard */
    status().then(function(s){if(String(s.version)!==version())refreshBoard();}).catch(function(){});
  },20000);
}
})();"""
