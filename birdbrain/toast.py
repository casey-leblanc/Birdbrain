"""Notices on this PC: shown one at a time through the tray icon, and a click on one opens the list on that card.

notices.py decides what to say and when. This module shows it: at most one notification each half minute, however
many came due together (after the PC wakes, say), so they never arrive as a batch. It also remembers which card the
last one was about, for the click.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime

from notices import Notice, Notices

log = logging.getLogger(__name__)

BALLOON_CLICK = 0x0405   # Windows: NIN_BALLOONUSERCLICK, sent to the tray icon when its notification is clicked


class Toasts:
    def __init__(self, show, notices: Notices, open_list, enabled=lambda: True):
        """`show(title, text)` puts a notification on screen, while `enabled()` says they're wanted on this PC;
        `open_list()` brings Birdbrain's window up. Anything in `also` is handed each notice too (the phone)."""
        self.show, self.notices, self.open_list, self.enabled = show, notices, open_list, enabled
        self.also: list = []
        self.waiting: deque[Notice] = deque()
        self.last: Notice | None = None
        self.asks, self.asked_at = 0, 0.0     # clicks so far, and when the last one was: the page moves to that card
        self.lock = threading.Lock()

    def tick(self, now: datetime | None = None) -> Notice | None:
        """Call every half minute. Shows one notice if any is due or waiting; returns it."""
        with self.lock:
            try:
                self.waiting.extend(self.notices.due(now))
            except Exception:
                log.exception("Couldn't work out what's due")
            return self._next()

    def tell(self, notice: Notice | None) -> None:
        """Something to say right now (new work after a scan). It waits its turn behind anything already waiting."""
        if notice:
            with self.lock:
                self.waiting.append(notice)
                if len(self.waiting) == 1:
                    self._next()

    def _next(self) -> Notice | None:
        if not self.waiting:
            return None
        n = self.waiting.popleft()
        log.info("Notice: %s (%d card%s)", n.key.split(":")[0], len(n.ids), "" if len(n.ids) == 1 else "s")
        if self.enabled():
            self.last = n
            try:
                self.show(n.title, n.text)
            except Exception:
                log.exception("Couldn't show a notification")
        for tell in self.also:
            try:
                tell(n)
            except Exception:
                log.exception("Couldn't pass a notice on")
        return n

    def clicked(self) -> None:
        """The notification was clicked: the window comes up on the card it was about."""
        self.asks += 1
        self.asked_at = time.time()
        log.info("Notification clicked: opening the list on its card")
        self.open_list()

    def view(self) -> dict:
        """For the list page: which card to move to, how many times that has been asked, and when."""
        return {"n": self.asks, "id": self.last.ids[0] if self.last and self.last.ids else "", "at": self.asked_at}


def hear_clicks(icon, on_click) -> bool:
    """Have `on_click()` called when a notification from this tray icon is clicked. Windows only: pystray shows the
    notification but doesn't report the click, so the icon's own message handler is wrapped. Returns whether it
    could be."""
    handlers, notify = getattr(icon, "_message_handlers", None), getattr(icon, "_on_notify", None)
    if not isinstance(handlers, dict) or notify is None:
        return False
    for message, handler in list(handlers.items()):
        if handler == notify:
            def heard(wparam, lparam, _handler=handler):
                if lparam & 0xFFFF == BALLOON_CLICK:
                    threading.Thread(target=on_click, daemon=True, name="notice-click").start()
                    return 0
                return _handler(wparam, lparam)
            handlers[message] = heard
            return True
    return False
