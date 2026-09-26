"""Builds the list page. The markup is shared by both layouts; the stylesheet decides:
glass.py for the default Frosted glass layout, CSS below for the Classic layout, which
keeps the locked visual language (ROUND-2-CONTEXT.md, direction E).

  Now        overdue work, today, tomorrow
  This week  the following five days, one group per day
  Later      exams, quizzes, events and assignments further out

In Classic, the three bands are columns set straight on the canvas under large, light
monospaced headings. Exams: accent colour and bold. Quizzes: one step lower,
semi-bold with an italic "quiz" label. Controls are words, not icons.

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

import filters
import glass
import prefs as prefs_mod
import theme
from config import REPORT_PATH, Settings
from jev import EXAM_RE, QUIZ_RE
from store import Item, Store

SOURCE = {"moodle": "Moodle", "outlook-mail": "Email", "outlook-calendar": "Outlook calendar",
          "manual": "Added by you"}
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
                                    pool=everything)

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
            Column("Later", [Group("Exams", [i for i in later if test_level(i) == "exam"], "date"),
                             Group("Quizzes", [i for i in later if test_level(i) == "quiz"], "date"),
                             Group("Events", [i for i in later if i.kind == "event"], "date"),
                             Group("Assignments", [i for i in later if i.kind == "assignment"], "date")],
                   "Nothing further out yet.", kinds=False),
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
    """A course code in the monospaced structure face, with your nickname/colour if set."""
    mine = courses.get(code, {})
    style = f' style="color:{e(mine["color"])};--cc:{e(mine["color"])}"' if mine.get("color") else ""
    return (f'<span class="code" data-code="{e(code)}"{style} title="{e(code) if mine.get("nick") else ""}">'
            f'{e(mine.get("nick") or code)}</span>')


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
            f'{e(title)}</a>' if i.url
            else f'<span class="t" title="{e(tip)}">{e(title)}</span>')
    meta = ""
    if level and kinds:
        meta += f'<span class="kind">{level}</span>'
    meta += _code(code, courses)
    meta += f'<time class="w{" late" if urgent else ""}" datetime="{i.due:%Y-%m-%dT%H:%M}">{e(_when(i, now, when))}</time>'
    if i.needs_review and not (reason or done):
        meta += '<span class="unsure" title="This date was read from text; double-check it">date unsure</span>'

    did = f"d{zlib.crc32(i.id.encode()):x}"
    acts = (f'<span class="acts needs-app"><button type="button" class="act edit">Edit</button>'
            f'<button type="button" class="act del">Delete</button></span>' if i.source == "manual" else "")
    if done:
        stamp = f"{i.done_at:%a, %b} {i.done_at.day} at {_time(i.done_at)}"
        tail = f'<p class="detail">Completed {e(stamp)}. Untick to put it back. {acts}</p>'
    elif reason:
        tail = f'<p class="detail">Hidden: {e(reason)}</p>'
    elif detail := _detail(i):
        meta += (f'<button class="act more" type="button" aria-expanded="false" aria-controls="{did}">'
                 f'Details</button>')
        tail = f'<p class="detail" id="{did}" hidden>{e(detail)} {acts}</p>'
    else:
        tail = ""
    classes = "row" + (f" {level}" if level else "") + (" is-done" if done else "") + (
        " past" if not (reason or done) and i.kind != "assignment" and i.due < now else "")
    checked = " checked" if done else ""
    fields = f' data-manual="{e(_manual_fields(i))}"' if i.source == "manual" else ""
    if not (reason or done) and (due := urgency(i, now)):
        fields += f' data-due="{due}"'
    return (f'<li class="{classes}" data-id="{e(i.id)}"{fields}><label class="tickwrap">'
            f'<input class="tick" type="checkbox"{checked} aria-label="{"Not done" if done else "Done"}: {e(title)}">'
            f'</label><div class="body">{name}<p class="meta">{meta}</p>{tail}</div></li>')


# --- page -----------------------------------------------------------------------
def _column(c: Column, now: datetime, courses: dict) -> str:
    slug = re.sub(r"\W+", "-", c.title.lower())
    body = ""
    for g in c.groups:
        if g.items:
            rows = "".join(_row(i, g.when, now, courses, kinds=c.kinds, urgent=g.urgent) for i in g.items)
            due = f' data-due="{g.due}"' if g.due else ""
            body += f'<h3 class="grp{" urgent" if g.urgent else ""}"{due}>{e(g.label)}</h3><ul>{rows}</ul>'
    body = body or f'<p class="empty">{e(c.empty)}</p>'
    noun = "item" if c.count == 1 else "items"
    return (f'<section class="band" aria-labelledby="h-{slug}"><h2 id="h-{slug}">{e(c.title)}'
            f'<span class="n">{c.count}<span class="sr"> {noun}</span></span></h2>{body}</section>')


def _counts(b: Board) -> str:
    on = lambda n, c: f' class="{c}"' if n else ""
    return (f'<span{on(b.overdue, "o")} data-due="overdue">{b.overdue} overdue</span>'
            f'<span{on(b.due_today, "on")} data-due="today">{b.due_today} today</span>'
            f'<span{on(b.tomorrow, "on")} data-due="tomorrow">{b.tomorrow} tomorrow</span>')


def _next(level: str, items: list[Item], settings: Settings, now: datetime, courses: dict) -> str:
    one, many = ("exam", "exams") if level == "exam" else ("quiz", "quizzes")
    span = f"{len(items)} {one if len(items) == 1 else many} in the next {settings.lookahead_days} days"
    if not items:
        return (f'<div class="nx {level}"><p class="k">Next {one}</p>'
                f'<p class="none">None in the next {settings.lookahead_days} days.</p></div>')
    # Prefer an entry whose date came straight from Moodle/Outlook over one read from text.
    nxt = next((i for i in items if not i.needs_review), items[0])
    when = _when_long(nxt, now) + (", date unsure" if nxt.needs_review else "")
    due = f' data-due="{u}"' if (u := urgency(nxt, now)) else ""
    return (f'<div class="nx {level}"{due}><p class="k">Next {one} <span class="span">{e(span)}</span></p>'
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
        out += _bin("archived", "Archived", f"Duplicates, plus entries matching your hidden keywords ({kws}). "
                    "Change keywords from the tray icon: Hide entries by keyword…", rows, len(b.archived),
                    opened.get("archived", False))
    return f'<div class="bins">{out}</div>' if out else ""


def render_board(b: Board, settings: Settings, status: str, now: datetime, version: int = 0,
                 prefs: dict | None = None) -> str:
    """Everything inside the page wrapper; the live page swaps this in after a change."""
    prefs = prefs or prefs_mod.DEFAULTS
    courses = prefs["courses"]
    warn = "sign-in" in status.lower() or "failed" in status.lower()
    return "".join([
        '<header class="top">',
        '<h1>Birdbrain</h1>',
        f'<p class="status{" problem" if warn else ""}">{e(status)}</p>',
        f'<div class="today"><p class="date">{now:%A, %B} {now.day}</p><p class="counts">{_counts(b)}</p></div>',
        '<nav class="actions needs-app" aria-label="Actions">',
        '<button id="open-add" class="act strong" type="button" aria-haspopup="dialog">Add item</button>',
        '<button id="open-settings" class="act" type="button" aria-haspopup="dialog">Settings</button></nav>',
        '</header>',
        '<section class="next" aria-label="Next exam and quiz">',
        _next("exam", b.exams, settings, now, courses), _next("quiz", b.quizzes, settings, now, courses),
        "</section>",
        '<main class="bands">', "".join(_column(c, now, courses) for c in b.columns), "</main>",
        _bins(b, settings, now, courses, prefs["bins"]),
        f'<span id="board-meta" hidden data-version="{version}"></span>',
    ])


def keyword_counts(b: Board, keywords: list[str]) -> list[dict]:
    """How many entries each hidden keyword is keeping off the list."""
    return [{"keyword": k, "count": sum(1 for h in b.archived if filters.keyword_hit(h.item, [k]))} for k in keywords]


def _theme_options(glass_layout: bool, photo) -> str:
    """One card per theme; its light (day) and dark (night) halves are each a choice. In the glass
    layout the halves show the theme's photos, in classic its colours."""
    cards = ""
    for key, th in theme.THEMES.items():
        halves = ""
        for mode in ("light", "dark"):
            t = th["modes"][mode]
            word = ("Day" if mode == "light" else "Night") if glass_layout else mode.capitalize()
            radio = (f'<input type="radio" name="look" value="{key}:{mode}" '
                     f'aria-label="{e(th["name"])}, {word.lower()}">')
            thumb = photo(glass.photo_name(key, mode, thumb=True)) if glass_layout else None
            if thumb:
                halves += (f'<label class="half photo" style="background-image:url(&quot;{e(thumb)}&quot;)">'
                           f'{radio}<span>{word}</span></label>')
            else:
                halves += (f'<label class="half" style="background:{t["bg"]}">{radio}'
                           f'<span style="color:{t["text"]}">Aa</span> <span style="color:{t["struct"]}">Now</span> '
                           f'<span style="color:{t["accent"]}">exam</span></label>')
        cards += (f'<div class="theme-opt"><div class="swatch">{halves}</div>'
                  f'<span class="theme-name">{e(th["name"])}</span></div>')
    return cards


def _settings_dialog(b: Board, now: datetime, glass_layout: bool, photo, settings: Settings) -> str:
    layouts = "".join(f'<label><input type="radio" name="layout" value="{v}"><span>{label}</span></label>'
                      for v, label in (("glass", "Frosted glass"), ("classic", "Classic")))
    rows = "".join(
        f'<li data-code="{e(c)}"><input type="color" aria-label="Colour for {e(c)}">'
        f'<span class="cc">{e(c)}</span>'
        f'<input type="text" class="nick" maxlength="24" placeholder="Nickname" aria-label="Nickname for {e(c)}">'
        f'<button type="button" class="act reset">Reset</button><p class="warn" aria-live="polite"></p></li>'
        for c in b.courses)
    courses = (f'<ul class="courses">{rows}</ul>' if rows
               else '<p class="hint">Course codes appear here after the next scan.</p>')
    since = (now.date() - timedelta(days=30)).isoformat()
    return (
        '<dialog id="settings" class="sheet-dialog" aria-labelledby="settings-title"><div class="sheet">'
        '<div class="sheet-head"><h2 id="settings-title">Settings</h2>'
        '<button type="button" class="act" data-close>Close</button></div>'
        f'<section class="set-sec"><h3>Layout</h3><div class="seg layout" role="radiogroup" aria-label="Layout">{layouts}</div>'
        '<p class="hint">Frosted glass sets your list in glass panels over a photo; Classic is flat and typographic.</p></section>'
        '<section class="set-sec"><h3>Theme</h3>'
        f'<div class="themes" role="radiogroup" aria-label="Theme">{_theme_options(glass_layout, photo)}</div>'
        '<label class="check"><input type="checkbox" id="follow-system">'
        "<span>Follow Windows' light and dark mode</span></label></section>"
        '<section class="set-sec needs-app"><h3>Scanning</h3>'
        f'<p class="hint">Birdbrain checks Moodle and Outlook every {settings.interval_minutes} minutes.</p>'
        '<div class="btn-row"><button type="button" class="btn" id="scan-now">Scan now</button>'
        '<button type="button" class="btn" id="scan-full">Full rescan of Moodle</button>'
        '<button type="button" class="btn" id="sign-in">Sign in to Moodle and Outlook</button></div>'
        '<div class="sound-row"><label class="check"><input type="checkbox" id="sound-on">'
        '<span>Squawk when something new is due</span></label>'
        '<button type="button" class="act" id="sound-test">Play the squawk</button></div>'
        '<p class="hint" id="scan-now-msg" aria-live="polite"></p>'
        '<p class="hint">Regular scans read your newest emails. To catch older ones, scan the inbox back to a date.</p>'
        '<div class="scan-row"><label class="field"><span>Scan back to</span>'
        f'<input type="date" id="scan-since" value="{since}" max="{now.date().isoformat()}"></label>'
        '<button type="button" class="btn" id="scan-go">Scan inbox</button></div>'
        '<p class="hint" id="scan-msg" aria-live="polite"></p></section>'
        '<section class="set-sec needs-app"><h3>Hidden keywords</h3>'
        '<p class="hint">Entries whose title or course contains one of these words move to Archived.</p>'
        '<ul class="kw-list" id="kw-list"></ul>'
        '<form class="kw-add" id="kw-form" novalidate><label class="field"><span>Add a keyword</span>'
        '<input id="kw-input" maxlength="80" autocomplete="off"></label>'
        '<button type="submit" class="btn">Hide these entries</button></form>'
        '<p class="form-error" id="kw-error" role="alert"></p></section>'
        '<section class="set-sec"><h3>Courses</h3>'
        '<p class="hint">Give each course code its own colour and a nickname. Changes apply right away.</p>'
        f'{courses}</section>'
        '<section class="set-sec needs-app"><h3>App</h3>'
        '<p class="hint">The settings file holds the scan interval, how far ahead to look and other options.</p>'
        '<div class="btn-row"><button type="button" class="btn" data-open="settings">Open settings file</button>'
        '<button type="button" class="btn" data-open="log">Open log</button>'
        '<button type="button" class="btn danger" id="quit-app">Quit Birdbrain</button></div>'
        '</section></div></dialog>')


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


def render(b: Board, settings: Settings, status: str, now: datetime, token: str = "", version: int = 0,
           prefs: dict | None = None, app_window: bool = False) -> str:
    prefs = prefs or prefs_mod.DEFAULTS
    mode = prefs["mode"] if prefs["mode"] in ("dark", "light") else theme.DEFAULT_MODE
    # "Match system" is resolved in the browser before the first paint.
    head_js = ("var r=document.documentElement;if(r.dataset.modePref==='system')"
               "r.dataset.mode=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';")
    glass_layout = prefs["layout"] == "glass"
    # Photos come from Birdbrain's own server on the live page, and straight from disk in the read-only copy.
    photo = (lambda n: f"/bg/{n}.jpg?token={token}") if token else glass.file_url
    page_data = json.dumps({"prefs": prefs, "themes": list(theme.THEMES), "modes": list(theme.MODES),
                            "keywords": keyword_counts(b, settings.hidden_keywords)})
    page_data = page_data.replace("</", "<\\/")   # can't close the <script> early
    return "".join([
        f'<!doctype html><html lang="en"{' class="app-window"' if app_window and token else ''} data-layout="{e(prefs["layout"])}" data-theme="{e(prefs["theme"])}" data-mode="{mode}" '
        f'data-mode-pref="{e(prefs["mode"])}">'
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta name="birdbrain-token" content="{e(token)}">' if token else "",
        f"<title>Birdbrain, {now:%a %b} {now.day}</title><script>{head_js}</script>",
        f"<style>{theme.font_face_css()}{theme.css_tokens()}{glass.css(photo) if glass_layout else CSS}"
        f"{TITLEBAR_CSS}{SCROLL_CSS}</style></head>",
        f'<body class="{"live" if token else "static"}"><div class="wrap">',
        render_board(b, settings, status, now, version, prefs),
        f'</div>{_settings_dialog(b, now, glass_layout, photo, settings)}{_item_dialog(b, now)}',
        '<div id="toast" role="status" aria-live="polite"></div>',
        '<div class="gscroll" aria-hidden="true"><i></i></div>',
        _TITLEBAR if app_window and token else "",
        f'<script type="application/json" id="page-data">{page_data}</script>',
        f"<script>{JS}</script></body></html>",
    ])


_TITLEBAR = ('<div class="titlebar"><div class="edge" data-edge="top"></div><div class="edge l" data-edge="topleft"></div>'
             '<div class="edge r" data-edge="topright"></div><div class="drag"></div>'
             '<button type="button" class="win-btn" id="win-min" aria-label="Minimize" title="Minimize">&#xE921;</button>'
             '<button type="button" class="win-btn" id="win-max" aria-label="Maximize" title="Maximize">'
             '<span class="max">&#xE922;</span><span class="res">&#xE923;</span></button>'
             '<button type="button" class="win-btn close" id="win-close" aria-label="Close" title="Close">&#xE8BB;</button></div>')


def write(store: Store, settings: Settings, status: str) -> tuple[str, int]:
    """Write the read-only copy (today.html); returns (path, count due today)."""
    now = datetime.now()
    b = build(store, settings, now)
    REPORT_PATH.write_text(render(b, settings, status, now, prefs=prefs_mod.load(store)), encoding="utf-8")
    return str(REPORT_PATH), b.due_today


CSS = """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:400 16px/1.45 "Birdbrain Sans","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body.static .needs-app{display:none!important}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
p,h1,h2,h3,ul{margin:0;padding:0}ul{list-style:none}
.wrap{max-width:1360px;margin:0 auto;padding:6vh 5vw 10vh;container-type:inline-size}
:focus-visible{outline:2px solid var(--focus);outline-offset:3px;border-radius:2px}

/* header: title with the scan status under it, today, actions */
.top{display:grid;grid-template-columns:auto minmax(0,1fr) auto;grid-template-areas:"title today actions" "status status .";column-gap:4rem;row-gap:.6rem;align-items:end;margin-bottom:3.5rem}
h1{grid-area:title;font-size:3.052rem;font-weight:800;letter-spacing:-.03em;line-height:.95;color:var(--head)}
.status{grid-area:status;font-size:.8rem;color:var(--muted)}
.status.problem{color:var(--accent)}
.today{grid-area:today}
.today .date{color:var(--muted)}
.counts{display:flex;flex-wrap:wrap;column-gap:1.6rem;color:var(--muted)}
.counts .o{color:var(--accent);font-weight:800}
.actions{grid-area:actions;display:flex;gap:.5rem;align-self:start}

/* text buttons */
.act{position:relative;font:inherit;font-size:.8rem;font-weight:600;color:var(--muted);background:none;border:0;padding:4px 6px;min-height:28px;cursor:pointer;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px}
.act::before{content:"";position:absolute;inset:-8px -2px}   /* 44px hit area, same look */
.act:hover{color:var(--text)}
.actions .act{font-size:1rem;min-height:44px;padding:8px 10px;color:var(--text);white-space:nowrap}
.actions .act.strong{font-weight:800;color:var(--struct);text-decoration-thickness:2px}
.btn{font:inherit;font-weight:600;min-height:44px;padding:0 18px;color:var(--struct);background:none;border:1px solid var(--line);border-radius:4px;cursor:pointer}
.btn:hover{border-color:var(--struct)}
.btn.primary{background:var(--struct);border-color:var(--struct);color:var(--col)}
.btn:disabled{opacity:.5;cursor:default}

/* next exam / next quiz: on the bands' column grid; label, title and date rows line up across both */
.next{display:grid;grid-template-columns:minmax(0,1fr);column-gap:3.5rem;margin-bottom:4.5rem}
.nx{display:grid;grid-row:span 3;grid-template-rows:subgrid;align-content:start}
.nx+.nx{margin-top:1.5rem}
.nx .k{font-weight:600;color:var(--muted)}
.nx.exam .k{color:var(--accent)}
.nx .span{font-weight:400;color:var(--muted);margin-left:.6rem}
.nx .t{font-size:1.25rem;font-weight:600;line-height:1.2;margin:.1rem 0 .2rem}
.nx.exam .t{font-size:1.563rem;font-weight:800}
.nx .none{color:var(--muted)}
.nx .meta{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:.7rem;color:var(--muted)}

/* the three bands: 1, 2 or 3 columns by width, with thin see-through bars in the gutters */
.bands{display:grid;grid-template-columns:minmax(0,1fr);gap:3.5rem;--rule:color-mix(in srgb,var(--struct) 30%,transparent)}
.band{position:relative;min-width:0}
.band+.band::before{content:"";position:absolute;top:-1.75rem;left:0;right:0;height:1px;background:var(--rule);pointer-events:none}
@container (min-width:37.5rem){
.next,.bands{grid-template-columns:repeat(2,minmax(0,1fr))}
.nx+.nx{margin-top:0}
.band:nth-child(2)::before{top:0;bottom:0;left:-1.75rem;right:auto;width:1px;height:auto}
.band:nth-child(3)::before{right:auto;width:calc(200% + 3.5rem)}}
@container (min-width:58rem){
.next,.bands{grid-template-columns:repeat(3,minmax(0,1fr))}
.band+.band::before{top:0;bottom:0;left:-1.75rem;right:auto;width:1px;height:auto}}
.band h2{font:300 2.441rem/1 "Birdbrain Mono",ui-monospace,monospace;color:var(--struct);letter-spacing:-.03em;margin-bottom:.6rem;display:flex;align-items:baseline;gap:.8rem}
.n{font:400 .8rem/1 "Birdbrain Sans",sans-serif;color:var(--muted);letter-spacing:0}
.grp{font:italic 400 1rem/1.2 "Birdbrain Sans",sans-serif;color:var(--muted);margin:1.4rem 0 .4rem}
.grp.urgent{color:var(--accent)}
.empty{color:var(--muted);margin-top:1rem}

/* items */
.row{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:.225rem;align-items:start;padding:.45rem 0}
.tickwrap{display:grid;place-items:center;width:44px;height:44px;margin:-10px 0 -10px -13px;cursor:pointer}
.tick{appearance:none;width:18px;height:18px;margin:0;border:1.5px solid var(--muted);border-radius:3px;display:grid;place-items:center;cursor:pointer;background:none}
.tick:checked{background:var(--text);border-color:var(--text)}
.tick:checked::after{content:"";width:5px;height:9px;border:solid var(--bg);border-width:0 2px 2px 0;transform:translateY(-1px) rotate(45deg)}
.tick:disabled{cursor:default;opacity:.6}
.t{display:block;font-size:1rem;line-height:1.3;color:var(--text);text-decoration:none;overflow-wrap:anywhere}
a.t:hover{text-decoration:underline;text-underline-offset:3px}
.row.exam .t{color:var(--accent);font-weight:800}
.row.quiz .t{font-weight:600}
.row .meta{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:.7rem;row-gap:.1rem;margin-top:.15rem;font-size:.8rem;color:var(--muted)}
.kind{font-style:italic}
.row.exam .kind{color:var(--accent);font-weight:600}
.code{font:500 .8rem/1.3 "Birdbrain Mono",ui-monospace,monospace;color:var(--struct);letter-spacing:-.01em}
.w.late{color:var(--accent);font-weight:800}
.unsure{font-style:italic}
.row.past .t,.row.past .w{color:var(--muted)}
.row.is-done .t{color:var(--muted);text-decoration:line-through;font-weight:400}
.row.leaving{opacity:0;transform:translateX(6px);transition:opacity .18s ease-in,transform .18s ease-in}
.detail{font-size:.8rem;color:var(--muted);margin-top:.35rem;max-width:36rem;overflow-wrap:anywhere}
.acts{display:inline-flex;gap:.2rem;margin-left:.2rem}
.act.del{color:var(--accent)}

/* completed + archived */
.bins{margin-top:5rem;display:grid;gap:2.5rem}
.bin summary{position:relative;list-style:none;display:flex;flex-wrap:wrap;align-items:baseline;gap:.4rem .9rem;cursor:pointer;width:fit-content;padding:2px 0}
.bin summary::-webkit-details-marker{display:none}
.bin summary::before{content:"";position:absolute;inset:-4px 0}
.bin-title{font:300 1.953rem/1.1 "Birdbrain Mono",ui-monospace,monospace;color:var(--struct);letter-spacing:-.03em}
.bin.archived .bin-title{color:var(--muted)}
.state{font-size:.8rem;font-weight:600;color:var(--muted);text-decoration:underline;text-underline-offset:3px}
.state::after{content:"Show"}
.bin[open] .state::after{content:"Hide"}
.bin summary:hover .state{color:var(--text)}
.bin summary.pulse .bin-title{animation:pulse 1s ease-out}
@keyframes pulse{from{color:var(--accent)}}
.hint{font-size:.8rem;color:var(--muted);margin:.4rem 0 .8rem;max-width:40rem}
.bin-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,17rem),1fr));column-gap:3.5rem;align-items:start}

/* dialogs */
.sheet-dialog{width:min(620px,calc(100vw - 32px));max-height:min(88vh,940px);padding:0;border:1px solid var(--line);border-radius:6px;background:var(--col);color:var(--text)}
.sheet-dialog::backdrop{background:rgba(10,10,20,.5)}
.sheet-dialog[open]{animation:sheet-in .2s ease-out}
@keyframes sheet-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.sheet{padding:24px 28px 28px;margin:0}
.sheet-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.4rem}
.sheet-head h2{font:300 1.953rem/1 "Birdbrain Mono",ui-monospace,monospace;color:var(--struct);letter-spacing:-.03em}
.set-sec{padding-top:1.6rem}
.set-sec h3{font:italic 400 1rem/1.2 "Birdbrain Sans",sans-serif;color:var(--muted);margin-bottom:.7rem}
.themes{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px 12px;margin-bottom:1rem}
.theme-opt{position:relative;display:grid;gap:6px;cursor:pointer}
.theme-opt input,.seg input{position:absolute;opacity:0;pointer-events:none}
.swatch{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:4px;overflow:hidden}
.half{padding:9px 7px;font-size:.8rem;font-weight:600;white-space:nowrap;overflow:hidden}
.theme-name{font-size:.8rem;color:var(--muted)}
.half{position:relative;cursor:pointer}
.half:hover{filter:brightness(1.06)}
.half:has(input:checked){box-shadow:inset 0 0 0 2px #FFFFFF,inset 0 0 0 4px #000000}
.theme-opt:has(input:checked) .theme-name{color:var(--text);font-weight:600}
.theme-opt:has(input:focus-visible) .swatch{outline:2px solid var(--focus);outline-offset:4px}
.seg{display:flex;flex-wrap:wrap;gap:.2rem 1.2rem}
.seg label{position:relative;cursor:pointer}
.seg span{display:inline-block;padding:12px 0;color:var(--muted);font-weight:400}
.seg label:hover span{color:var(--text)}
.seg input:checked+span{color:var(--text);font-weight:800;text-decoration:underline;text-decoration-color:var(--struct);text-decoration-thickness:2px;text-underline-offset:6px}
.seg label:has(input:focus-visible){outline:2px solid var(--focus);outline-offset:2px}
fieldset.field{border:0;padding:0;margin:0 0 1rem}
.field{display:grid;gap:6px;margin:0 0 1rem;min-width:0}
.field>span,.field legend{font-size:.8rem;font-weight:600;color:var(--muted);padding:0}
.field em{font-style:italic;font-weight:400}
.field input{font:inherit;font-size:1rem;color:var(--text);background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:10px 12px;min-height:44px;min-width:0;width:100%}
.field input:focus{border-color:var(--struct);outline:2px solid var(--focus);outline-offset:1px}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-error{font-size:1rem;color:var(--accent);margin-bottom:.6rem}.form-error:empty{display:none}
.actions-row{display:flex;justify-content:flex-end;align-items:center;gap:1rem;margin-top:.6rem}
.scan-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px}.scan-row .field{margin:0;flex:1 1 200px}
.btn-row{display:flex;flex-wrap:wrap;gap:10px;margin:.2rem 0 .4rem}
.check{display:flex;align-items:center;gap:10px;min-height:44px;cursor:pointer;color:var(--text)}
.check input{width:18px;height:18px;margin:0;flex:none;accent-color:var(--struct)}
.sound-row{display:flex;flex-wrap:wrap;align-items:center;gap:0 18px}
:root{--tb-fg:var(--text);--tb-hover:color-mix(in srgb,var(--text) 12%,transparent);--tb-scrolled:color-mix(in srgb,var(--bg) 88%,transparent);
 --sb-track:transparent;--sb-track-edge:transparent;--sb-blur:none;--sb-bevel:none;
 --sb-thumb:color-mix(in srgb,var(--struct) 38%,transparent);--sb-thumb-hover:color-mix(in srgb,var(--struct) 62%,transparent);--sb-thumb-edge:transparent}
.sheet-dialog::-webkit-scrollbar{width:14px}
.sheet-dialog::-webkit-scrollbar-track{background:transparent;margin:10px 0}
.sheet-dialog::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--struct) 38%,transparent);border:4px solid transparent;background-clip:padding-box;border-radius:999px}
.sheet-dialog::-webkit-scrollbar-thumb:hover{background-color:color-mix(in srgb,var(--struct) 62%,transparent)}
.btn.danger{color:var(--accent);border-color:var(--accent)}
.kw-list li{display:flex;flex-wrap:wrap;align-items:center;gap:4px 14px;padding:6px 0;border-bottom:1px solid var(--line)}
.kw{font-weight:600}.kw-n{flex:1;font-size:.8rem;color:var(--muted)}.kw-empty{color:var(--muted);font-style:italic;border:0!important}
.kw-add{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px;margin-top:.8rem}.kw-add .field{margin:0;flex:1 1 220px}
.gone{font-size:1.25rem;color:var(--muted);margin:4rem 0}
.courses li{display:grid;grid-template-columns:32px minmax(96px,auto) 1fr auto;grid-template-areas:"color code nick reset" ". warn warn warn";align-items:center;column-gap:12px;padding:6px 0}
.courses input[type=color]{grid-area:color;appearance:none;-webkit-appearance:none;width:44px;height:44px;padding:8px;margin:-8px;border:0;border-radius:50%;background:none;cursor:pointer}
.courses input[type=color]::-webkit-color-swatch-wrapper{padding:0}
.courses input[type=color]::-webkit-color-swatch{border:1px solid var(--line);border-radius:50%}
.cc{grid-area:code;font:500 1rem/1.2 "Birdbrain Mono",ui-monospace,monospace;color:var(--struct);white-space:nowrap}
.nick{grid-area:nick;min-width:0;width:100%;font:inherit;font-size:1rem;color:var(--text);background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:8px 10px}
.nick::placeholder{color:var(--muted)}
.nick:focus{border-color:var(--struct);outline:2px solid var(--focus);outline-offset:1px}
.reset{grid-area:reset}
.reset:disabled{opacity:.45;cursor:default;text-decoration:none}
.courses .warn{grid-area:warn;font-size:.8rem;color:var(--accent);margin-top:2px}.courses .warn:empty{display:none}
#toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,10px);max-width:calc(100vw - 32px);padding:10px 16px;border-radius:4px;background:var(--text);color:var(--bg);font-weight:600;opacity:0;pointer-events:none;transition:opacity .2s ease-out,transform .2s ease-out}
#toast.show{opacity:1;transform:translate(-50%,0)}
@media (max-width:760px){.wrap{padding:28px 18px 60px}
.top{grid-template-columns:1fr auto;grid-template-areas:"title actions" "status status" "today today";row-gap:.8rem;column-gap:1rem}
h1{font-size:2.441rem}.band h2{font-size:1.953rem}
.sheet{padding:18px}.field-row{grid-template-columns:1fr}
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
.titlebar .edge.l,.titlebar .edge.r{width:10px}.titlebar .edge.l{cursor:nw-resize}.titlebar .edge.r{left:auto;cursor:ne-resize}
.maximized .titlebar .edge{display:none}
.win-btn{width:46px;height:32px;border:0;border-radius:0;padding:0;background:transparent;color:var(--tb-fg);text-shadow:var(--tb-shadow,none);font:10px/1 "Segoe Fluent Icons","Segoe MDL2 Assets",sans-serif;display:grid;place-items:center;cursor:default;transition:background-color .1s}
.win-btn:hover{background:var(--tb-hover)}
.win-btn.close:hover{background:#C42B1C;color:#FFFFFF}
.win-btn:focus-visible{outline:2px solid currentColor;outline-offset:-4px;border-radius:0}
.win-btn .res{display:none}.maximized .win-btn .max{display:none}.maximized .win-btn .res{display:inline}
@media (prefers-reduced-motion:reduce){.titlebar,.win-btn{transition:none}}
"""

SCROLL_CSS = """
/* the page's own scrollbar (Windows' one is hidden): it floats over the page, starts under the title bar,
   rests faintly, and comes forward while you scroll or point at it. Colours come from the layout (--sb-*). */
html{scrollbar-width:none}html::-webkit-scrollbar{display:none}
.gscroll{display:none;position:fixed;top:8px;bottom:8px;right:4px;width:10px;z-index:45;border-radius:999px;
 background:var(--sb-track);border:1px solid var(--sb-track-edge);-webkit-backdrop-filter:var(--sb-blur);backdrop-filter:var(--sb-blur);
 opacity:.6;transition:opacity .25s ease-out,width .15s ease-out}
.app-window .gscroll{top:38px}
.gscroll.on{display:block}
.gscroll.moving,.gscroll:hover,.gscroll.active{opacity:1}
.gscroll:hover,.gscroll.active{width:14px}
.gscroll i{position:absolute;left:1px;right:1px;top:0;border-radius:999px;background:var(--sb-thumb);border:1px solid var(--sb-thumb-edge);
 box-shadow:var(--sb-bevel);-webkit-backdrop-filter:var(--sb-blur);backdrop-filter:var(--sb-blur);transition:background-color .15s}
.gscroll i:hover,.gscroll.active i{background:var(--sb-thumb-hover)}
@media (prefers-reduced-motion:reduce){.gscroll,.gscroll i{transition:none}}
"""

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
function refreshBoard(){
  return fetch('/board?token='+encodeURIComponent(TOKEN)).then(function(r){
    if(!r.ok)throw new Error(GONE);return r.text();})
  .then(function(h){wrap.innerHTML=h;bindBoard();});
}
var toastTimer;
function toast(msg){var t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');
  clearTimeout(toastTimer);toastTimer=setTimeout(function(){t.classList.remove('show');},2800);}
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
      var done=box.checked;li.classList.add('leaving');
      api('/api/done',{id:li.dataset.id,done:done}).then(refreshBoard).then(function(){
        if(done){var s=document.querySelector('.bin.completed summary');
          if(s){s.classList.remove('pulse');void s.offsetWidth;s.classList.add('pulse');}
          toast('Moved to Completed');}
        else toast('Put back on your list');
      }).catch(function(err){box.checked=!done;li.classList.remove('leaving');toast("Couldn't save: "+err.message);});
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
    api('/api/items/delete',{id:btn.closest('.row').dataset.id}).then(refreshBoard).then(function(){toast('Deleted');})
      .catch(function(err){toast(err.message);});});});
  document.querySelectorAll('.bin[data-bin]').forEach(function(d){
    /* Browsers also fire "toggle" for a bin that is built already open; only save real changes,
       or saving would bump the version and refresh the page in a loop. */
    d.addEventListener('toggle',function(){if(!!PREFS.bins[d.dataset.bin]===d.open)return;
      PREFS.bins[d.dataset.bin]=d.open;var b={};b[d.dataset.bin]=d.open;savePrefs({bins:b});});});
  var gear=document.getElementById('open-settings');
  if(gear)gear.addEventListener('click',function(){syncCourseInputs();settings.showModal();});
  var add=document.getElementById('open-add');
  if(add)add.addEventListener('click',function(){openItemForm(null,null);});
}

/* --- dialogs ------------------------------------------------------------ */
var settings=document.getElementById('settings'),itemDlg=document.getElementById('add-item'),itemForm=document.getElementById('add-form');
[settings,itemDlg].forEach(function(d){
  d.addEventListener('click',function(ev){if(ev.target===d)d.close();});
  d.querySelectorAll('[data-close]').forEach(function(b){b.addEventListener('click',function(){d.close();});});
});

/* add / edit your own items (one form; editing just fills it in first) */
var editing=null;
function openItemForm(fields,id){
  var f=itemForm.elements;editing=id;
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
  api(editing?'/api/items/update':'/api/items',data).then(refreshBoard).then(function(){
    itemDlg.close();toast((editing?'Saved “':'Added “')+data.title+'”');
    if(!editing){f.title.value='';f.time.value='';f.notes.value='';}
  }).catch(function(e){err.textContent=e.message;}).then(function(){go.disabled=false;});
});

/* theme + mode */
var media=matchMedia('(prefers-color-scheme: light)');
function applyTheme(){
  root.classList.add('no-anim');   /* switch colours instantly, not via hover transitions */
  root.dataset.theme=PREFS.theme;root.dataset.modePref=PREFS.mode;
  root.dataset.mode=PREFS.mode==='system'?(media.matches?'light':'dark'):PREFS.mode;syncCourseInputs();syncLook();
  requestAnimationFrame(function(){requestAnimationFrame(function(){root.classList.remove('no-anim');});});}
media.addEventListener('change',function(){if(PREFS.mode==='system')applyTheme();});
/* each theme's day (light) and night (dark) halves are the choices */
var followSys=document.getElementById('follow-system');
function syncLook(){settings.querySelectorAll('input[name=look]').forEach(function(r){
  r.checked=r.value===PREFS.theme+':'+root.dataset.mode;});followSys.checked=PREFS.mode==='system';}
settings.querySelectorAll('input[name=look]').forEach(function(r){r.addEventListener('change',function(){
  var v=r.value.split(':');PREFS.theme=v[0];PREFS.mode=v[1];applyTheme();savePrefs({theme:v[0],mode:v[1]});});});
followSys.addEventListener('change',function(){PREFS.mode=followSys.checked?'system':root.dataset.mode;
  applyTheme();savePrefs({mode:PREFS.mode});});
syncLook();
/* Each layout has its own stylesheet, so switching layout saves and reloads the page. */
settings.querySelectorAll('input[name=layout]').forEach(function(r){
  r.checked=r.value===PREFS.layout;
  r.addEventListener('change',function(){if(!LIVE){toast('Open the list from the Birdbrain icon to change the layout');return;}
    api('/api/prefs',{layout:r.value}).then(function(){location.reload();}).catch(function(e){toast("Couldn't save: "+e.message);});});});
/* the squawk when something new is due */
var soundOn=document.getElementById('sound-on');soundOn.checked=PREFS.sound!==false;
soundOn.addEventListener('change',function(){PREFS.sound=soundOn.checked;savePrefs({sound:soundOn.checked});});
document.getElementById('sound-test').addEventListener('click',function(){api('/api/sound').catch(function(e){toast(e.message);});});

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
    kwInput=document.getElementById('kw-input'),kwError=document.getElementById('kw-error');
function renderKw(){kwList.textContent='';
  if(!KW.length){var none=document.createElement('li');none.className='kw-empty';none.textContent='No hidden keywords.';kwList.appendChild(none);return;}
  KW.forEach(function(k,i){var li=document.createElement('li'),w=document.createElement('span'),n=document.createElement('span'),
    rm=document.createElement('button');
    w.className='kw';w.textContent=k.keyword;n.className='kw-n';n.textContent=k.count+(k.count===1?' entry':' entries')+' hidden';
    rm.type='button';rm.className='act';rm.textContent='Remove';rm.setAttribute('aria-label','Stop hiding “'+k.keyword+'”');
    rm.addEventListener('click',function(){saveKw(KW.filter(function(_,j){return j!==i;}).map(function(x){return x.keyword;}),
      'No longer hiding “'+k.keyword+'”');});
    li.appendChild(w);li.appendChild(n);li.appendChild(rm);kwList.appendChild(li);});}
function saveKw(list,msg){kwError.textContent='';
  return api('/api/keywords',{keywords:list}).then(function(r){KW=r.keywords;renderKw();refreshBoard();toast(msg);})
    .catch(function(e){kwError.textContent=e.message;});}
kwForm.addEventListener('submit',function(ev){ev.preventDefault();var v=kwInput.value.split(' ').filter(Boolean).join(' ').trim();
  if(!v){kwError.textContent='Type a word to hide.';kwInput.focus();return;}
  if(KW.some(function(k){return k.keyword.toLowerCase()===v.toLowerCase();})){kwError.textContent='“'+v+'” is already hidden.';return;}
  saveKw(KW.map(function(k){return k.keyword;}).concat([v]),'Hiding entries with “'+v+'”').then(function(){kwInput.value='';});});
renderKw();

/* inbox scan back to a date */
var scanGo=document.getElementById('scan-go'),scanMsg=document.getElementById('scan-msg');
function watchScan(){var iv=setInterval(function(){status().then(function(s){scanMsg.textContent=s.status;
  if(!s.scanning){clearInterval(iv);scanGo.disabled=false;refreshBoard();}}).catch(function(){clearInterval(iv);scanGo.disabled=false;});},2000);}
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
    el.style.color=c.color||'';el.style.setProperty('--cc',c.color||'');});
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
    li.querySelector('.cc').style.color=c.color||'';li.querySelector('.cc').style.setProperty('--cc',c.color||'');
    var nick=li.querySelector('.nick');if(document.activeElement!==nick)nick.value=c.nick||'';
    li.querySelector('.reset').disabled=!(c.nick||c.color);
    if(PREFS.layout!=='glass'&&ratio(col,bg)<4.5)msgs.push('Hard to read on this theme ('+ratio(col,bg).toFixed(1)+':1, needs 4.5). Try a '+(lum(bg)<.2?'lighter':'darker')+' colour.');
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
    if(['light','night-light','paper','aubergine'].indexOf(t)>=0){patch.theme='night';patch.mode='light';}
    else{if(t==='dark')t='night';if(DATA.themes.indexOf(t)>=0)patch.theme=t;if(DATA.modes.indexOf(old.mode)>=0)patch.mode=old.mode;}
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
    status().then(function(s){if(String(s.version)!==version())refreshBoard();}).catch(function(){});
  },20000);
}
})();"""
