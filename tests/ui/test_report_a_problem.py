"""Report a problem: the window shows every line that would go in the zip, scrubbed, and saves only that."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from page import PageTest

import trouble
from config import LOG_PATH

LOG = """2026-11-18 09:02:40 INFO moodle: Signed in as jdoe12@lsu.edu
2026-11-18 09:03:05 INFO moodle: Reading 2026 Fall CHEM 1212 for A. Teacher (course 3 of 8)
2026-11-18 09:03:09 INFO moodle: found 'Biochemical Testing - Oxidase Test' at https://moodle.lsu.edu/mod/quiz/view.php?id=1
2026-11-18 09:04:00 ERROR main: Scan crashed
KeyError: 'timeline'"""


class ReportAProblem(PageTest):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.revealed: list[Path] = []
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(LOG, encoding="utf-8")
        super().setUp()

    def actions(self) -> dict:
        return {"problem": lambda body: trouble.action(self.store, body, self.status, folder=self.folder, reveal=self.revealed.append)}

    def open_window(self):
        self.page.keyboard.press("m")
        self.page.locator("#app-menu [data-menu=problem]").click()
        self.page.locator("#problem[open]").wait_for()
        self.page.locator("#problem-files details").first.wait_for()

    def shown(self) -> str:
        return "\n".join(self.page.locator("#problem-files pre").all_text_contents())

    def test_everything_that_would_go_in_is_shown_and_nothing_personal_is_in_it(self):
        self.open_window()
        names = self.page.locator("#problem-files summary .fold-t").all_inner_texts()
        self.assertEqual(names, ["about.txt", "settings.txt", "log.txt"])
        text = self.shown()
        for gone in ("jdoe12", "lsu.edu", "CHEM 1212", "A. Teacher", "Oxidase"):
            self.assertNotIn(gone, text)
        for kept in ("Scan crashed", "KeyError: 'timeline'", "[email]", "[course]", "[title]", "[address]", "Birdbrain 2."):
            self.assertIn(kept, text)
        self.assertIn("sends nothing", self.page.locator("#problem").inner_text())
        self.assertEqual(list(self.folder.iterdir()), [], "looking saves nothing")

    def test_your_own_words_are_scrubbed_and_shown_before_saving(self):
        self.open_window()
        self.page.locator("#problem-note").fill("My CHEM 1212 quiz vanished. I'm jdoe12@lsu.edu")
        self.page.keyboard.press("Tab")
        self.page.locator("#problem-files summary .fold-t", has_text="what-happened.txt").wait_for()
        self.assertIn("My [course] quiz vanished. I'm [email]", self.shown())

    def test_saving_writes_exactly_what_was_shown_and_says_where(self):
        self.open_window()
        self.page.locator("#problem-note").fill("the list is empty after a scan")
        self.page.locator("#problem-save").click()
        self.page.locator("#problem-msg", has_text="Nothing was sent anywhere").wait_for()
        (saved,) = list(self.folder.iterdir())
        self.assertIn(saved.name, self.page.locator("#problem-msg").inner_text())
        self.assertEqual(self.revealed, [saved])                                # shown in its folder
        with zipfile.ZipFile(saved) as z:
            inside = {n: z.read(n).decode("utf-8") for n in z.namelist()}
        shown = dict(zip(self.page.locator("#problem-files summary .fold-t").all_inner_texts(),
                         self.page.locator("#problem-files pre").all_text_contents()))
        self.assertEqual(inside, shown)
        self.assertEqual(inside["what-happened.txt"], "the list is empty after a scan")

    def test_it_is_a_command_too_and_esc_closes_without_saving(self):
        self.page.keyboard.press("Control+k")
        self.page.keyboard.type("report")
        self.page.keyboard.press("Enter")
        self.page.locator("#problem[open]").wait_for()
        self.page.keyboard.press("Escape")
        self.page.locator("#problem").wait_for(state="hidden")
        self.assertEqual(list(self.folder.iterdir()), [])


class ReportInFocus(ReportAProblem):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
