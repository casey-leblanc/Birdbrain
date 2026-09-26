"""Outlook on the web: inbox previews and calendar week views.

Only the message list is read, so no email is opened and nothing gets
marked as read. Jev decides which previews describe an assignment, test
or event, and reads the date out of them.

Outlook's page markup is not a public API; the selectors below target its
accessibility roles, which change less often than its CSS class names.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta

from dateutil import parser as dparser
from playwright.sync_api import BrowserContext, Page

from browser import NeedsLogin, complete_sign_in, on_ms_login
from config import Settings
from jev import Jev
from store import Item, Store, text_hash

log = logging.getLogger(__name__)

_MAIL_JS = """(limit) => [...document.querySelectorAll('[role="listbox"] [role="option"]')]
  .slice(0, limit)
  .map(el => ({id: el.getAttribute('data-convid') || el.id || '',
               label: el.getAttribute('aria-label') || '', text: el.innerText || ''}))"""

# Scroll whichever ancestor of the message list actually scrolls.
_SCROLL_JS = """el => { let n = el;
  while (n && !(n.scrollHeight > n.clientHeight + 10 && /auto|scroll/.test(getComputedStyle(n).overflowY))) n = n.parentElement;
  n = n || el; n.scrollBy(0, n.clientHeight * 0.9); }"""
MAX_DEEP_SCAN = 3000   # messages; safety cap for "scan back to a date"

_CAL_JS = """() => [...document.querySelectorAll('[role="main"] [role="button"][aria-label]')]
  .map(el => el.getAttribute('aria-label'))
  .filter(l => /\\d{1,2}:\\d{2}|all day/i.test(l))"""

# Outlook also labels empty slots in the week grid (the one nearest "now" when the page opens, or a
# selected one) as "9:00 PM to 9:30 PM, Friday, September 25, 2026". Real events start with their subject.
_EMPTY_SLOT = re.compile(r"^(\d{1,2}:\d{2}\s*[AP]M\s*(to|-|–)\s*\d{1,2}:\d{2}\s*[AP]M|all[- ]day( event)?)$", re.I)

_WEEKDAY_DATE = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Z][a-z]+ \d{1,2}, \d{4})")
_TIME = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", re.I)


class Outlook:
    def __init__(self, settings: Settings, store: Store, jev: Jev):
        self.s = settings
        self.base = settings.outlook_url.rstrip("/")
        self.store = store
        self.jev = jev

    def _open(self, ctx: BrowserContext, path: str, ready: str) -> Page:
        page = ctx.new_page()
        page.goto(self.base + path, wait_until="domcontentloaded")
        page.wait_for_timeout(1_500)  # Outlook bounces through Microsoft sign-in to refresh tokens
        if on_ms_login(page.url) and not complete_sign_in(page, lambda u: not on_ms_login(u)):
            url = page.url
            page.close()
            raise NeedsLogin(f"Outlook sign-in stopped at {url}")
        try:
            page.wait_for_selector(ready, timeout=45_000)
        except Exception:
            if on_ms_login(page.url):
                page.close()
                raise NeedsLogin(f"Outlook sign-in stopped at {page.url}")
            raise
        return page

    def scan(self, ctx: BrowserContext) -> list[Item]:
        new: list[Item] = []
        if self.s.scan_outlook_mail:
            new += self._scan_mail(ctx)
        if self.s.scan_outlook_calendar:
            new += self._scan_calendar(ctx)
        return new

    # --- mail -----------------------------------------------------------------
    def scan_mail_since(self, ctx: BrowserContext, since: date, progress=None) -> list[Item]:
        """One-off deeper scan: read the inbox back to `since` instead of just
        the newest `email_scan_count` messages."""
        return self._scan_mail(ctx, since=since, progress=progress)

    def _scan_mail(self, ctx: BrowserContext, since: date | None = None, progress=None) -> list[Item]:
        page = self._open(ctx, "/mail/inbox", '[role="listbox"] [role="option"]')
        today = date.today()
        # The list is virtualised (only rows near the viewport exist), so collect
        # rows as we scroll. Newest first: once several rows in a row are older
        # than `since`, we're past it (a pinned old message alone won't stop us).
        rows: dict[str, dict] = {}
        older_streak, stale_rounds = 0, 0
        max_rows = MAX_DEEP_SCAN if since else self.s.email_scan_count
        for _ in range(MAX_DEEP_SCAN // 5 if since else 10):
            before = len(rows)
            for r in page.evaluate(_MAIL_JS, max_rows):
                key = r["id"] or text_hash(r["text"])
                if key in rows:
                    continue
                rows[key] = r
                if since:
                    old = _received_date(r["text"] or r["label"], today) < since
                    older_streak = older_streak + 1 if old else 0
            if progress and since:
                progress(len(rows))
            stale_rounds = stale_rounds + 1 if len(rows) == before else 0
            if len(rows) >= max_rows or (since and older_streak >= 5) or stale_rounds >= 3:
                break  # enough, reached the date, or hit the end of the inbox
            page.locator('[role="listbox"]').first.evaluate(_SCROLL_JS)
            page.wait_for_timeout(700)
        page.close()

        new = []
        for key, r in list(rows.items())[:max_rows]:
            text = r["text"] or r["label"]
            if since and _received_date(text, today) < since:
                continue
            h = text_hash("mail|" + text)
            if self.store.already_judged(h):
                continue
            sent = _received_date(text, today)
            j = self.jev.judge(text, sent=sent)
            item_id = f"outlook:mail:{h[:16]}"
            self.store.mark_judged(h, item_id)
            if not Jev.is_actionable(j) or not j.due or j.due < today - timedelta(days=self.s.overdue_days):
                continue
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            subject = lines[1] if len(lines) > 1 else lines[0] if lines else "(email)"
            item = Item(id=item_id, source="outlook-mail", kind=j.kind, title=subject[:140],
                        due=datetime.combine(j.due, time(23, 59)), course=lines[0][:60] if lines else "",
                        url=self.base + "/mail/inbox", detail=" ".join(lines[2:])[:300],
                        confidence=j.confidence, needs_review=j.needs_review)
            if self.store.upsert(item):
                new.append(item)
        return new

    # --- calendar ---------------------------------------------------------------
    def _scan_calendar(self, ctx: BrowserContext) -> list[Item]:
        new, keep = [], set()
        start = date.today() - timedelta(days=date.today().weekday())
        weeks = self.s.lookahead_days // 7 + 1
        for w in range(weeks):
            d = start + timedelta(weeks=w)
            try:
                page = self._open(ctx, f"/calendar/view/week/{d.year}/{d.month}/{d.day}", '[role="main"]')
                page.wait_for_timeout(2500)  # events render after the grid
                labels = page.evaluate(_CAL_JS)
                page.close()
            except NeedsLogin:
                raise
            except Exception:
                log.exception("Calendar week %s failed", d)
                return new  # incomplete: don't prune
            for label in labels:
                item = self._calendar_item(label)
                if not item:
                    continue
                keep.add(item.id)
                if self.store.upsert(item):
                    new.append(item)
        self.store.remove_missing("outlook:cal:", keep)
        return new

    def _calendar_item(self, label: str) -> Item | None:
        title = label.split(",")[0].strip()
        if not title or _EMPTY_SLOT.match(title):
            return None   # an empty time slot, not an event
        m, t = _WEEKDAY_DATE.search(label), _TIME.search(label)
        if m:
            day = dparser.parse(m.group(2)).date()
            when = datetime.combine(day, dparser.parse(t.group(1)).time() if t else time(0, 0))
            conf, review = None, False
        else:  # unfamiliar label format (other locale): let Jev read it
            j = self.jev.judge(label, role="the date of this calendar event")
            if not j.due:
                return None
            when, conf, review = datetime.combine(j.due, time(0, 0)), j.confidence, j.needs_review
        kind = self._kind(title)
        if "recurring" in label.lower() and kind != "test":
            return None  # weekly lectures etc. would drown out the real reminders
        return Item(id=f"outlook:cal:{text_hash(title + when.isoformat())[:16]}", source="outlook-calendar",
                    kind=kind, title=title[:140], due=when, url=self.base + "/calendar/",
                    detail=label[len(title) + 1:][:300].strip(), confidence=conf, needs_review=review)

    def _kind(self, title: str) -> str:
        key = "kind:" + text_hash("cal|" + title)
        cached = self.store.get_meta(key)
        if not cached:
            cached = self.jev.classify_title(title, "calendar")
            self.store.set_meta(key, cached)
        return cached


def _received_date(text: str, today: date) -> date:
    """Outlook's list shows '10:32 AM' (today), 'Wed 9/23' (this week) or '9/12/2026'."""
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if m:
        mo, dy, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(yr) + (2000 if yr and len(yr) == 2 else 0) if yr else today.year
        try:
            d = date(year, mo, dy)
            return d if d <= today else date(year - 1, mo, dy)
        except ValueError:
            pass
    m = re.search(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", text)
    if m and not _TIME.search(text):
        back = (today.weekday() - ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].index(m.group(1))) % 7
        return today - timedelta(days=back)
    return today
