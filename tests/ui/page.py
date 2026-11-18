"""For UI tests: Birdbrain's own list page, served by its own server with invented items, in headless Chromium.

    python -m unittest discover tests/ui

Needs Playwright's Chromium (python -m playwright install chromium). BIRDBRAIN_TEST_CHROME can name another
Chrome or Chromium to use instead.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import helpers  # noqa: E402,F401  (a throwaway data folder, and the import path)

from playwright.sync_api import sync_playwright  # noqa: E402

import prefs  # noqa: E402
import report  # noqa: E402
from config import Settings  # noqa: E402
from server import ListServer  # noqa: E402
from store import Item  # noqa: E402

CHEM = "2026 Fall CHEM 1212 for A. Teacher"


def invented(now: datetime) -> list[Item]:
    """A week of made-up work: three labs the rules once called exams, a real exam, a quiz and an errand."""
    day = lambda n, h=23, m=59: (now + timedelta(days=n)).replace(hour=h, minute=m, second=0, microsecond=0)
    return [
        Item("moodle:cm:1", "moodle", "test", "Biochemical Testing - Oxidase Test", day(0), CHEM, "https://example.edu/1"),
        Item("moodle:cm:2", "moodle", "test", "Biochemical Testing - Catalase Test", day(1), CHEM, "https://example.edu/2"),
        Item("moodle:cm:3", "moodle", "test", "Biochemical Testing - Urease Test", day(3), CHEM, "https://example.edu/3"),
        Item("moodle:cal:4", "moodle", "test", "Exam 2", day(2, 9, 30), "2026 Fall MATH 1550 for B. Teacher"),
        Item("moodle:cm:5", "moodle", "test", "Chapter 7 Quiz", day(1, 17, 0), "2026 Fall MATH 1550 for B. Teacher", level="quiz"),
        Item("moodle:cm:6", "moodle", "assignment", "Essay 2 draft", day(-1), "2026 Fall ENGL 2000 for C. Teacher"),
        Item("manual:7", "manual", "event", "Dentist", day(1, 15, 0), ""),
    ]


class PageTest(unittest.TestCase):
    """Each test gets a fresh store with the invented items, a running server and an open page."""
    layout = "glass"
    needs_sign_in: list[str] = []   # sites the page should say need signing in to again
    status = "Updated 10:32 AM."    # what the app says about its last scan

    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        chrome = os.environ.get("BIRDBRAIN_TEST_CHROME")
        try:
            cls._browser = cls._pw.chromium.launch(executable_path=chrome) if chrome else cls._pw.chromium.launch()
        except Exception:
            cls._pw.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def setUp(self):
        self.store, self.settings = helpers.store(), Settings()
        for i in invented(datetime.now()):
            self.store.upsert(i)
        prefs.update(self.store, {"layout": self.layout, "sound": False})
        s = self.store
        board = lambda: report.build(s, self.settings)
        self.server = ListServer(
            s, render_page=lambda t: report.render(board(), self.settings, self.status, datetime.now(), t, s.version,
                                                   prefs.load(s), sign_in=self.needs_sign_in),
            render_board=lambda t: report.render_board(board(), self.settings, self.status, datetime.now(), s.version,
                                                       prefs.load(s), sign_in=self.needs_sign_in),
            status=lambda: {"version": s.version, "status": self.status, "scanning": False, "progress": None,
                             "signing_in": False, "inbox": False},
            request_mail_scan=lambda d: None, on_change=lambda: None, actions=self.actions())
        self.server.start()
        self.context = self._browser.new_context(viewport={"width": 1280, "height": 900})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.open()

    def open(self):
        self.page.goto(self.server.url)
        self.page.wait_for_selector(".row")

    def tearDown(self):
        self.context.close()
        self.server.stop()
        self.assertEqual(self.errors, [], "the page threw a script error")

    def actions(self) -> dict:
        """The app's own actions the page may call (scan, quit, ...); a test adds the ones it needs."""
        return {}

    def row(self, title: str):
        return self.page.locator(".row", has_text=title).first

    def stored(self, item_id: str) -> Item:
        return self.store.get(item_id)
