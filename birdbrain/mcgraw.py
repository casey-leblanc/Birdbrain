"""McGraw Hill Connect: the student's upcoming assignments, read from Connect's own pages when signed in
(connect.mheducation.com), in the same browser session as Moodle and Outlook. Nothing is sent anywhere.

Many courses reach Connect through Moodle instead: a McGraw Hill link in the Moodle course signs the student in (an
LTI launch), and Connect's own sign-in page doesn't work for them. For those, the sign-in window has the student click
such a link once (browser.ConnectWatch), and this reader then uses the sign-in Moodle handed over. When it runs out,
the reader re-opens that same link through Moodle (browser.relaunch_connect), but only if the student turned that on.

Connect (newconnect.mheducation.com) lists assignments in two places: the To Do list, which only covers the next few
days, and each class's own page (/student/class/section/<id>), which lists all of them. Some courses link Moodle to the
class page; others link each Moodle activity to a single assignment, so the student may never see a class page. Either
way, Connect's addresses name the class, so this reads the To Do list and every class page named anywhere: on the way in
from Moodle (browser.ConnectWatch), in the To Do list's links, or on the class list or calendar in Connect's own menu.
It reads them as assignment cards: a name, "Start: ... Due: Oct 2, 2026 at
11:59 PM CDT", and the class ("Fall 2026 CHEM 1212 Connect Lab"). Work already completed, submitted or scored
is left off (and comes off the list once it is). A due date read without a time is marked "date unsure".
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from dateutil import parser as dparser
from playwright.sync_api import BrowserContext

from browser import NeedsLogin, relaunch_connect
from config import Settings
from jev import EXAM_RE, QUIZ_RE
from store import Item, Store, text_hash

log = logging.getLogger(__name__)

# Each assignment's card: its name, course, link and words. Connect draws every assignment (on the To Do list and on a
# class's own page) as an "assignment-card": the name as a heading, "Start: ... Due: Oct 2, 2026 at 11:59 PM CDT", and
# the class ("Fall 2026 CHEM 1212 Connect Lab"). If that ever changes, any block that says "due" with a date
# is grown out to the largest box around it that holds just that one due date, and read the same way.
_TODO_JS = r"""() => {
  // a block's words with a space between its parts (innerText runs inline parts together: "HomeworkDue: ...")
  const words = el => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), out = [];
    for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.data.trim(); if (t) out.push(t); } return out.join(' '); };
  const DUE = /\bdue\b/i, DATE = /(\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b|\b\d{1,2}\/\d{1,2}(\/\d{2,4})?\b)/i,
        CODE = /\b[A-Z]{2,4}\s?\d{4}\b/, dues = t => (t.match(/due/gi) || []).length;
  let cards = [...document.querySelectorAll('.assignment-card')];
  if (!cards.length) {
    const dated = [...document.querySelectorAll('body *')].filter(el => { const t = el.textContent; return t.length < 700 && /due/i.test(t) && DATE.test(t); });
    const inner = dated.filter(el => !dated.some(o => o !== el && el.contains(o)));
    const grow = el => { let c = el;
      while (c.parentElement && c.parentElement !== document.body) { const t = c.parentElement.textContent;
        if (t.length > 700 || dues(t) > dues(c.textContent)) break; c = c.parentElement; }
      return c; };
    cards = [...new Set(inner.map(grow))];
  }
  const pageClass = [...document.querySelectorAll('h1, h2, [role=heading]')].map(words).find(t => CODE.test(t) && t.length < 140) || '';
  return cards.map(el => ({el, text: words(el)})).filter(c => DUE.test(c.text) && DATE.test(c.text)).map(({el, text}) => {
    const head = el.querySelector('h2, h3, h4, [role=heading], [class*=title], [class*=Title]'), link = el.querySelector('a[href]');
    // the class: the shortest part of the card naming a course code, else the nearest heading above, else the page's
    let course = [...el.querySelectorAll('*')].map(words).filter(t => CODE.test(t) && t.length < 120).sort((a, b) => a.length - b.length)[0] || '';
    for (let n = el; n && !course; n = n.parentElement)
      for (let p = n.previousElementSibling; p && !course; p = p.previousElementSibling) {
        const h = p.matches('h1,h2,h3,[class*=course],[class*=Course]') ? p : p.querySelector && p.querySelector('h1,h2,h3');
        if (h && words(h).length < 120) course = words(h); }
    return {title: (head ? words(head) : '') || (link ? words(link) : '') || text.split(/\b(start|due)\b/i)[0].trim(),
            href: link ? link.href : '', course: course || pageClass, text};
  });
}"""

# The classes a page leads to: each class's own page, which lists every assignment (the To Do list only has the next few
# days), from any Connect link naming a class (a class page, or one assignment: /section/<id> or sectionId=<id>); and
# the class list or calendar in Connect's own menu, which name more of them.
_CLASSES_JS = r"""() => { const ids = new Set(), menus = new Set(), ID = /\/class\/section\/(\d+)|\/sections?\/(\d{6,})|[?&]section_?id=(\d{6,})/i;
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href.split('#')[0], path = href.split('?')[0], m = href.match(ID);
    if (!/^https:\/\/[^\/]*mheducation\.com\//i.test(href)) continue;
    if (m) ids.add(m[1] || m[2] || m[3]);
    else if (/^(my )?(classes|courses|calendar)$/i.test(a.textContent.replace(/\s+/g, ' ').trim()) && /\/student\/[a-z\/-]+$/i.test(path))
      menus.add(path);
  }
  return {sections: [...ids].map(id => 'https://newconnect.mheducation.com/student/class/section/' + id), menus: [...menus]}; }"""
PAGES_PER_SCAN = 10
TODO_URL = "https://newconnect.mheducation.com/student/todo"

_DUE_AT = re.compile(
    r"due\b[^0-9a-z]*(?:on\s+|by\s+|date\s*:?\s*)?"
    r"(?P<when>(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?"
    r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)"
    r"(?:,?\s*(?:at\s+)?\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)?)", re.I)
# finished work: "Completed", "Submitted", a score ("Score: 8/10", "8/10 pts"), or 100%. A bare "9/28" is a date, not a score.
# Connect's cards also offer "See report" once the work is handed in and its results are ready.
_DONE = re.compile(r"\b(completed|submitted|see report|see results|view results|score[d:]?"
                   r"|\d{1,3}(?:\.\d+)?\s*/\s*\d{1,3}(?:\.\d+)?\s*(?:pts|points)\b)|\b100\s*%", re.I)
# "Assignment is locked": not open yet (a later start date, still listed), or closed once its due date has passed,
# when it can't be done any more and doesn't belong on a to-do list
_LOCKED = re.compile(r"\b(?:assignment is )?locked\b", re.I)


def read_due(text: str, now: datetime) -> tuple[datetime | None, bool]:
    """The due date and time in a line of Connect's To Do list, and whether a time was given."""
    m = _DUE_AT.search(text)
    if not m:
        return None, False
    when = m.group("when")
    has_time = bool(re.search(r"\d\s*[ap]\.?m", when, re.I))
    try:
        d = dparser.parse(when, fuzzy=True, default=now.replace(hour=23, minute=59, second=0, microsecond=0))
    except (ValueError, OverflowError):
        return None, False
    if not re.search(r"\d{4}|/\d{2,4}\b", when) and d < now - timedelta(days=180):
        d = d.replace(year=d.year + 1)   # no year given: the next one
    return d, has_time


class McGraw:
    def __init__(self, settings: Settings, store: Store):
        self.s, self.store = settings, store
        # where the student's assignments are listed: Connect's To Do list, then each class's own page seen so far
        self.pages = [TODO_URL] + [u for u in (settings.mcgraw_sections or []) if u.startswith("https://")]

    @staticmethod
    def _open(page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)   # Connect draws its lists after loading
        except Exception:
            pass
        page.wait_for_timeout(1_000)

    @staticmethod
    def _signed_out(page) -> bool:
        return bool(re.search(r"login|signin|sign-in", page.url, re.I) or page.locator("input[type=password]").count())

    def scan(self, ctx: BrowserContext) -> list[Item]:
        page = ctx.new_page()
        try:
            self._open(page, self.pages[0])
            if self._signed_out(page) and relaunch_connect(ctx, self.s):   # through Moodle, if the student allowed it
                self._open(page, self.pages[0])
            if self._signed_out(page):
                raise NeedsLogin(f"McGraw Hill Connect sign-in needed at {page.url}")
            # the To Do list, then Connect's class list or calendar if its menu has them, then every class page named
            # anywhere (at most PAGES_PER_SCAN pages)
            urls, rows, read = list(self.pages), {}, []
            for i in range(PAGES_PER_SCAN):
                if i >= len(urls):
                    break
                if i:
                    self._open(page, urls[i])
                    if self._signed_out(page):
                        break
                leads = page.evaluate(_CLASSES_JS)
                for u in reversed(leads["menus"]):   # read next: they name the classes
                    if u not in urls:
                        urls.insert(i + 1, u)
                urls += [u for u in leads["sections"] if u not in urls]
                found = page.evaluate(_TODO_JS)
                read.append(f"{page.url.split('?')[0].split('mheducation.com')[-1]} ({len(found)})")
                for r in found:
                    title = " ".join(r["title"].split())[:200]
                    course = " ".join(r["course"].split())[:80] or "McGraw Hill Connect"
                    if title:
                        rows.setdefault("mcgraw:" + text_hash(f"{course}|{title}")[:16], {**r, "title": title, "course": course,
                                                                                            "page": page.url})
            sections = [u for u in urls[1:] if "/student/class/section/" in u][:6]
            if sections != (self.s.mcgraw_sections or [])[:6]:
                s = Settings.load()
                s.mcgraw_sections = sections
                s.save()
            now = datetime.now()
            oldest = now - timedelta(days=self.s.overdue_days)
            keep, new, finished = set(), [], 0
            for item_id, r in rows.items():
                due, has_time = read_due(r["text"], now)
                closed = due is not None and due < now and _LOCKED.search(r["text"])
                if _DONE.search(r["text"]) or closed:   # handed in, or past due and closed: nothing left to do
                    if self.store.exists(item_id):
                        self.store.delete(item_id)
                        finished += 1
                    continue
                if not due or due < oldest:
                    continue
                title = r["title"]
                kind = "test" if (EXAM_RE.search(title) or QUIZ_RE.search(title)) else "assignment"
                item = Item(item_id, "mcgraw", kind, title, due, r["course"], url=r["href"] or r["page"], needs_review=not has_time)
                keep.add(item_id)
                if self.store.upsert(item):
                    new.append(item)
            grace = timedelta(minutes=max(180, 3 * self.s.interval_minutes))
            gone = self.store.remove_missing("mcgraw:", keep, grace=grace) if rows else 0
            log.info("McGraw Hill Connect: read %s; %d assignments, %d open, %d new, %d finished, %d removed",
                     ", ".join(read), len(rows), len(keep), len(new), finished, gone)
            return new
        finally:
            page.close()
