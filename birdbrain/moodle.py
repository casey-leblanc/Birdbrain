"""Moodle scanning through the logged-in browser session.

Regular scan: Moodle's own AJAX web services (the ones the Dashboard timeline
and calendar use), called from inside the page so your session cookie and
sesskey authenticate them. No web-service token is needed.

Full scan (first run, or "Full rescan"): additionally walks every enrolled
course: the assignment and quiz index tables, plus the text of the course
page itself, which Jev reads for exam dates and deadlines that were only
written in prose (syllabus notes, section summaries, labels).
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, time, timedelta
from urllib.parse import parse_qs, urlparse

from dateutil import parser as dparser
from playwright.sync_api import BrowserContext, Page

from browser import NeedsLogin, moodle_sso
from config import CHUNK_CHARS, Settings
from jev import EXAM_RE, Jev
from store import Item, Store, text_hash

log = logging.getLogger(__name__)

# Only course-page chunks that mention a date or an assessment word are sent
# to Jev, which keeps the first scan's request count reasonable.
_PREFILTER = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b|\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"|\b(mon|tues?|wed(nes)?|thu(rs)?|fri|sat(ur)?|sun)(day)?\b|\b\d{1,2}/\d{1,2}\b"
    r"|\b(exam|midterm|final|quiz|test|due|deadline|presentation)\b",
    re.I,
)

_AJAX_JS = """async ([url, method, args]) => {
  const r = await fetch(url, {method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify([{index: 0, methodname: method, args: args}])});
  return await r.json();
}"""

_TABLES_JS = """() => [...document.querySelectorAll('table.generaltable')].map(t => ({
  headers: [...t.querySelectorAll('thead th')].map(th => th.innerText.trim()),
  rows: [...t.querySelectorAll('tbody tr')].map(tr => {
    const a = tr.querySelector('a[href*="/mod/"][href*="view.php"]');
    return {cells: [...tr.querySelectorAll('td, th')].map(td => td.innerText.trim()),
            name: a ? a.innerText.trim() : '', link: a ? a.href : ''};
  })
}))"""


def _plain(s: str) -> str:
    """Moodle's web services return names HTML-escaped ("FD&amp;C") and
    descriptions as HTML; store plain text and let the report escape once."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _level(title: str, module: str, kind: str) -> str:
    """A test from Moodle's quiz activity is a quiz unless its title says exam, midterm, final or test."""
    if module == "quiz" and kind == "test":
        return "exam" if EXAM_RE.search(title) else "quiz"
    return ""


def _cm_id(url: str) -> str | None:
    q = parse_qs(urlparse(url or "").query)
    return q.get("id", [None])[0] if "/mod/" in (url or "") else None


class Moodle:
    def __init__(self, settings: Settings, store: Store, jev: Jev):
        self.s = settings
        self.base = settings.moodle_url.rstrip("/")
        self.store = store
        self.jev = jev
        self.page: Page | None = None
        self.sesskey = ""

    # --- plumbing -------------------------------------------------------------
    def _connect(self, ctx: BrowserContext) -> None:
        self.page = ctx.new_page()
        self._open_dashboard()
        if not self.sesskey:
            # Session expired: press the Office 365 sign-in button, which
            # completes on its own while Microsoft remembers you.
            log.info("Moodle session expired (at %s); trying single sign-on", self.page.url)
            if not moodle_sso(self.page, self.base):
                raise NeedsLogin(f"Moodle sign-in stopped at {self.page.url}")
            self._open_dashboard()
            if not self.sesskey:
                raise NeedsLogin(f"Moodle still signed out after single sign-on ({self.page.url})")

    def _open_dashboard(self) -> None:
        resp = self.page.goto(self.base + "/my/", wait_until="domcontentloaded")
        if resp and resp.status == 403:
            raise RuntimeError(f"Moodle refused the request (HTTP 403) at {self.page.url}")
        self.sesskey = ""
        if urlparse(self.page.url).netloc == urlparse(self.base).netloc and "/login/" not in self.page.url:
            self.sesskey = self.page.evaluate("() => (window.M && M.cfg && M.cfg.sesskey) || ''")

    def _ajax(self, method: str, args: dict):
        url = f"{self.base}/lib/ajax/service.php?sesskey={self.sesskey}&info={method}"
        res = self.page.evaluate(_AJAX_JS, [url, method, args])
        first = res[0] if isinstance(res, list) else res
        if first.get("error"):
            exc = first.get("exception") or {}
            if exc.get("errorcode") in ("servicerequireslogin", "invalidsesskey"):
                raise NeedsLogin("Moodle")
            raise RuntimeError(f"{method}: {exc.get('message', first)}")
        return first["data"]

    def _kind(self, title: str, module: str) -> str:
        if module == "quiz":   # decided from the title alone (no Jev call), so nothing to cache
            return self.jev.classify_title(title, module)
        key = "kind:" + text_hash(module + "|" + title)
        cached = self.store.get_meta(key)
        if cached:
            return cached
        kind = self.jev.classify_title(title, module)
        self.store.set_meta(key, kind)
        return kind

    # --- public -----------------------------------------------------------------
    def scan(self, ctx: BrowserContext, full: bool, progress=None) -> list[Item]:
        """The timeline and calendar; a full scan also reads every course's pages. `progress(part, detail)` hears how
        far it has got (0 to 1), and what it's reading."""
        say = progress or (lambda part=0.0, detail="": None)
        say(0.0, "opening your dashboard")
        self._connect(ctx)
        courses = self._courses()
        say(0.05 if full else 0.4, "timeline and calendar")
        new = self._scan_action_events() + self._scan_calendar_events()
        if full:
            for n, (cid, cname) in enumerate(courses.items()):
                say(0.1 + 0.9 * n / len(courses), f"{cname} (course {n + 1} of {len(courses)})")
                log.info("Full scan of course %s", cname)
                new += self._scan_index(cid, cname, "assign")
                new += self._scan_index(cid, cname, "quiz")
                new += self._scan_course_page(cid, cname)
        self.page.close()
        return new

    def _courses(self) -> dict[int, str]:
        try:
            data = self._ajax("core_course_get_enrolled_courses_by_timeline_classification",
                              {"classification": "inprogress", "limit": 0, "offset": 0})
            return {c["id"]: _plain(c.get("shortname") or c["fullname"]) for c in data.get("courses", [])}
        except NeedsLogin:
            raise
        except Exception:
            log.exception("Could not list Moodle courses")
            return {}

    def _scan_action_events(self) -> list[Item]:
        """Dashboard timeline: open assignments, quizzes, etc. with deadlines.
        Moodle drops an event here once you've submitted/completed it."""
        now = datetime.now()
        frm = int((now - timedelta(days=self.s.overdue_days)).timestamp())
        to = int((now + timedelta(days=max(self.s.lookahead_days, 120))).timestamp())
        new, keep, after = [], set(), 0
        for _ in range(20):  # up to 1000 events
            args = {"timesortfrom": frm, "timesortto": to, "limitnum": 50,
                    "limittononsuspendedevents": True}
            if after:
                args["aftereventid"] = after
            events = self._ajax("core_calendar_get_action_events_by_timesort", args).get("events", [])
            for e in events:
                cm = _cm_id(e.get("url", "")) or f"e{e['id']}"
                item_id = f"moodle:cm:{cm}"
                keep.add(item_id)
                self.store.delete(f"moodle:idx:{cm}")  # timeline supersedes index-page copy
                title = _plain(e.get("activityname") or e.get("name", ""))
                module = e.get("modulename", "")
                kind = self._kind(title, module)
                item = Item(
                    id=item_id, source="moodle", kind=kind, title=title, level=_level(title, module, kind),
                    due=datetime.fromtimestamp(e["timesort"]),
                    course=_plain((e.get("course") or {}).get("shortname") or (e.get("course") or {}).get("fullname", "")),
                    url=e.get("url", ""), detail=_plain(e.get("name", "")),
                )
                if self.store.upsert(item):
                    new.append(item)
            if len(events) < 50:
                break
            after = events[-1]["id"]
        else:
            return new
        self.store.remove_missing("moodle:cm:", keep)  # submitted or removed
        return new

    def _scan_calendar_events(self) -> list[Item]:
        """Non-activity calendar entries (course/site/user events), where
        instructors often post exam dates."""
        new = []
        try:
            data = self._ajax("core_calendar_get_calendar_upcoming_view", {"courseid": 1, "categoryid": 0})
        except NeedsLogin:
            raise
        except Exception:
            log.exception("Upcoming calendar view failed")
            return new
        for e in data.get("events", []):
            if e.get("modulename"):
                continue  # activity deadlines come from the timeline scan
            title = _plain(e.get("name", ""))
            item = Item(
                id=f"moodle:cal:{e['id']}", source="moodle", kind=self._kind(title, ""), title=title,
                due=datetime.fromtimestamp(e["timestart"]),
                course=_plain((e.get("course") or {}).get("shortname", "")), url=e.get("url") or e.get("viewurl", ""),
                detail=_plain(e.get("description") or "")[:300],
            )
            if self.store.upsert(item):
                new.append(item)
        return new

    def _scan_index(self, cid: int, cname: str, module: str) -> list[Item]:
        new = []
        try:
            self.page.goto(f"{self.base}/mod/{module}/index.php?id={cid}", wait_until="domcontentloaded")
            tables = self.page.evaluate(_TABLES_JS)
        except Exception:
            log.exception("Index page %s for course %s failed", module, cid)
            return new
        now = datetime.now()
        for t in tables:
            hdr = [h.lower() for h in t["headers"]]
            due_col = next((i for i, h in enumerate(hdr) if re.search(r"due|close|deadline", h)), None)
            sub_col = next((i for i, h in enumerate(hdr) if re.search(r"submi|grade", h)), None)
            if due_col is None:
                continue
            for r in t["rows"]:
                cells = r["cells"]
                if not r["link"] or due_col >= len(cells):
                    continue
                if sub_col is not None and sub_col < len(cells):
                    st = cells[sub_col].lower()
                    if (re.search(r"submitted|\d", st) and not re.search(r"no submission|not submitted|no attempt", st)):
                        continue  # already done
                due = self._parse_date(cells[due_col])
                if not due or due < now - timedelta(days=self.s.overdue_days):
                    continue
                cm = _cm_id(r["link"])
                if self.store.exists(f"moodle:cm:{cm}"):
                    continue  # already tracked via the timeline
                kind = self._kind(r["name"], module)
                item = Item(id=f"moodle:idx:{cm}", source="moodle", kind=kind, title=r["name"],
                            level=_level(r["name"], module, kind), due=due, course=cname, url=r["link"])
                if self.store.upsert(item):
                    new.append(item)
        return new

    def _parse_date(self, text: str) -> datetime | None:
        text = text.strip()
        if not text or text in ("-", "—"):
            return None
        try:
            return dparser.parse(text, fuzzy=True)
        except (ValueError, OverflowError):
            j = self.jev.judge(text)
            return datetime.combine(j.due, time(23, 59)) if j.due else None

    def _scan_course_page(self, cid: int, cname: str) -> list[Item]:
        new = []
        url = f"{self.base}/course/view.php?id={cid}"
        try:
            self.page.goto(url, wait_until="domcontentloaded")
            text = self.page.inner_text("#region-main, [role=main]", timeout=15_000)
        except Exception:
            log.exception("Course page %s failed", cid)
            return new
        today = datetime.now().date()
        for chunk in _chunks(text):
            h = text_hash(f"{cid}|{chunk}")
            if not _PREFILTER.search(chunk) or self.store.already_judged(h):
                continue
            j = self.jev.judge(chunk)
            item_id = f"moodle:page:{cid}:{h[:12]}"
            self.store.mark_judged(h, item_id)
            if not Jev.is_actionable(j) or not j.due or j.due < today:
                continue
            item = Item(id=item_id, source="moodle", kind=j.kind, title=_headline(chunk),
                        due=datetime.combine(j.due, time(23, 59)), course=cname, url=url,
                        detail="From course page text (time not stated)", confidence=j.confidence,
                        needs_review=j.needs_review)
            if self.store.upsert(item):
                new.append(item)
        return new


def _chunks(text: str):
    buf = ""
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) > CHUNK_CHARS and buf:
            yield buf
            buf = ""
        buf += para + "\n"
    if buf:
        yield buf


def _headline(chunk: str) -> str:
    """Best line to show as the title: the first one that names the assessment."""
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    for ln in lines:
        if re.search(r"\b(exam|midterm|final|quiz|test|due|deadline|assignment|project|presentation)\b", ln, re.I):
            return ln[:140]
    return (lines[0] if lines else chunk)[:140]
