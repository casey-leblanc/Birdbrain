"""Gradescope: the student's courses this term and each one's assignments, read from the pages the student sees
when signed in (www.gradescope.com, or a school's own Gradescope address), in the same browser session as Moodle and
Outlook. Nothing is sent anywhere; Birdbrain only reads.

The dashboard (/account) lists courses by term, newest first; Birdbrain reads the student courses of the newest term.
Each course page has a table with one row per assignment: its name (a link, or a button when it can't be opened),
its status ("No Submission", "Submitted", or a score once graded) and its release, due and late-due times in <time>
elements' datetime attributes. Assignments already submitted or graded aren't listed, and come off the list once
they are, so a submitted homework never shows as overdue; Moodle's own entry for the same assignment, if it has one,
is ticked off too.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from dateutil import parser as dparser
from playwright.sync_api import BrowserContext

import filters
from browser import NeedsLogin
from config import Settings
from jev import EXAM_RE, QUIZ_RE
from store import Item, Store, text_hash

log = logging.getLogger(__name__)

# courses on the dashboard, in page order, with the term heading each sits under; staff courses are left out
_COURSES_JS = r"""() => { const out = []; let student = true, term = '';
  for (const el of document.querySelectorAll('h1, h2, .courseList--term, a.courseBox')) {
    if (el.matches('h1, h2')) { const t = el.textContent.toLowerCase();
      if (t.includes('instructor')) student = false; else if (t.includes('student')) student = true; continue; }
    if (el.classList.contains('courseList--term')) { term = el.textContent.trim(); continue; }
    const m = (el.getAttribute('href') || '').match(/\/courses\/(\d+)/);
    if (!student || !m) continue;
    const short = el.querySelector('.courseBox--shortname'), name = el.querySelector('.courseBox--name');
    out.push({id: m[1], short: (short || el).textContent.trim(), name: name ? name.textContent.trim() : '', term}); }
  return out; }"""

# one course's assignment table
_ASSIGNMENTS_JS = r"""() => [...document.querySelectorAll('#assignments-student-table tbody tr, table tbody tr[role=row]')]
  .map(tr => { const head = tr.querySelector('th') || tr.cells[0]; if (!head) return null;
    const a = head.querySelector('a[href]'), b = head.querySelector('[data-assignment-id]'), due = tr.querySelectorAll('time.submissionTimeChart--dueDate'),
          status = tr.querySelector('td');
    return {title: head.textContent.trim(), href: a ? a.href : '',
            id: b ? b.getAttribute('data-assignment-id') : a ? ((a.getAttribute('href').match(/assignments\/(\d+)/) || [])[1] || null) : null,
            status: status ? status.textContent.trim() : '', due: due[0] ? due[0].getAttribute('datetime') : null}; })
  .filter(r => r && r.title)"""


def _when(stamp: str | None) -> datetime | None:
    """Gradescope's "2026-09-30 23:59:00 -0500" as local time."""
    if not stamp:
        return None
    try:
        d = dparser.parse(stamp)
    except (ValueError, OverflowError):
        return None
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d


def submitted(status: str) -> bool:
    """Anything but "No Submission" means it's been handed in: "Submitted", a late submission, or a score."""
    s = " ".join(status.split()).lower()
    return bool(s) and "no submission" not in s and "not submitted" not in s


class Gradescope:
    def __init__(self, settings: Settings, store: Store):
        self.s, self.store = settings, store
        self.base = (settings.gradescope_url or "https://www.gradescope.com").rstrip("/")

    def scan(self, ctx: BrowserContext) -> list[Item]:
        """Read this term's assignments; returns the ones Birdbrain hadn't seen before."""
        page = ctx.new_page()
        try:
            page.goto(self.base + "/account", wait_until="domcontentloaded")
            if "/login" in page.url or page.locator("form#login-form, input[name='session[password]']").count():
                raise NeedsLogin(f"Gradescope sign-in needed at {page.url}")
            courses = page.evaluate(_COURSES_JS)
            if courses:
                courses = [c for c in courses if c["term"] == courses[0]["term"]]   # the newest term only
            now = datetime.now()
            oldest = now - timedelta(days=self.s.overdue_days)
            keep, new, done = set(), [], 0
            # Moodle's own copies of these assignments (a Moodle activity that links out to Gradescope never hears
            # about the submission): open ones in the window, to tick off when Gradescope says it's handed in
            moodle = [i for i in self.store.items_between(oldest - timedelta(days=21), now + timedelta(days=120))
                      if i.id.startswith(filters.STRUCTURED) and not i.done_at]
            for c in courses:
                page.goto(f"{self.base}/courses/{c['id']}", wait_until="domcontentloaded")
                for r in page.evaluate(_ASSIGNMENTS_JS):
                    key = r["id"] or text_hash(r["title"])[:12]
                    item_id = f"gradescope:{c['id']}:{key}"
                    if submitted(r["status"]):
                        if self.store.exists(item_id):   # handed in since the last scan: off the list
                            self.store.delete(item_id)
                            done += 1
                        self._tick_off_moodle_copy(r, c, moodle)
                        continue
                    due = _when(r["due"])
                    if not due or due < oldest:
                        continue
                    title = r["title"]
                    kind = "test" if (EXAM_RE.search(title) or QUIZ_RE.search(title)) else "assignment"
                    item = Item(item_id, "gradescope", kind, title, due, c["short"] or c["name"],
                                url=r["href"] or f"{self.base}/courses/{c['id']}")
                    keep.add(item_id)
                    if self.store.upsert(item):
                        new.append(item)
            # anything no longer listed (removed by the instructor, or its course left) goes after a grace period, so
            # one page that didn't load can't take a whole course off the list
            grace = timedelta(minutes=max(180, 3 * self.s.interval_minutes))
            gone = self.store.remove_missing("gradescope:", keep, grace=grace) if courses else 0
            log.info("Gradescope: %d courses, %d assignments open, %d new, %d handed in, %d removed",
                     len(courses), len(keep), len(new), done, gone)
            return new
        finally:
            page.close()

    def _tick_off_moodle_copy(self, r: dict, c: dict, moodle: list[Item]) -> None:
        """Handed in on Gradescope: tick off Moodle's entry for the same assignment, so it doesn't sit there overdue.
        Only under the strict same-assignment test (filters.same_assignment), and only when exactly one entry fits. The student can untick it if it was ever the wrong one."""
        due, title = _when(r["due"]), r["title"]
        if not due or not moodle:
            return
        probe = Item("gradescope:probe", "gradescope", "assignment", title, due, f"{c['short']} {c['name']}")
        fits = [m for m in moodle if not m.done_at and filters.same_assignment(probe, m)]
        if len(fits) == 1:
            self.store.set_done(fits[0].id, True)
            fits[0].done_at = datetime.now()
            log.info("Gradescope says %r is handed in; ticked off Moodle's %s", title, fits[0].id)
