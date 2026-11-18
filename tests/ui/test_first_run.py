"""First run in under a minute: choose LSU and there is nothing to type; then the list says what it is reading."""
from __future__ import annotations

import time
import unittest

from page import PageTest

import prefs
import report


class FirstRun(PageTest):
    status = "Not scanned yet."

    def setUp(self):
        self.asked: list[dict] = []
        self.done = False
        super().setUp()

    def page_html(self, token: str) -> str:
        if not self.done:
            return report.render_setup(token, prefs.load(self.store))
        return super().page_html(token)

    def actions(self) -> dict:
        def setup(body: dict) -> dict:
            self.asked.append(body)
            if not str(body.get("moodle", "")).startswith("https://"):
                raise ValueError("That doesn't look like a web address. It should start with https://")
            if not body.get("check"):
                for item_id in ("moodle:cm:1", "moodle:cm:2", "moodle:cm:3", "moodle:cal:4", "moodle:cm:5", "moodle:cm:6", "manual:7"):
                    self.store.delete(item_id)                                  # a first run has nothing on the list yet
                self.status = "Full Moodle scan: reading CHEM 1212 (course 2 of 6)"
                self.done = True
            return {"ok": True, "moodle": body["moodle"]}
        return {"setup": setup}

    def open(self):
        self.page.goto(self.server.url)
        self.page.wait_for_selector("#setup-form")


class ChoosingLSU(FirstRun):
    def test_lsu_is_two_presses_with_nothing_typed(self):
        began = time.time()
        self.assertTrue(self.page.locator("input[name=school][value=lsu]").is_checked())
        self.assertFalse(self.page.locator("input[name=moodle]").is_visible())  # no address to find or paste
        self.assertIn("Nothing to type", self.page.locator("#school-says").inner_text())
        self.page.keyboard.press("Enter")                                       # Continue
        self.page.locator("#step-look:visible").wait_for()
        self.assertEqual(self.asked[-1], {"check": True, "moodle": "https://moodle.lsu.edu", "outlook": "https://outlook.office.com",
                                          "no_outlook": False, "gradescope": False, "mcgraw": False})
        self.page.keyboard.press("Enter")                                       # Start Birdbrain
        self.page.locator(".clear.first").wait_for()                            # the list, already saying what it's doing
        saved = self.asked[-1]
        self.assertNotIn("check", saved)
        self.assertEqual((saved["moodle"], saved["outlook"], saved["layout"]), ("https://moodle.lsu.edu", "https://outlook.office.com", "glass"))
        self.assertLess(time.time() - began, 20, "two presses should take seconds, not a minute")

    def test_the_list_says_what_it_is_reading_while_the_first_scan_runs(self):
        self.page.keyboard.press("Enter")
        self.page.locator("#step-look:visible").wait_for()
        self.page.locator("#look-go").click()
        first = self.page.locator("#first-says")
        first.wait_for()
        self.assertEqual(first.inner_text(), "Full Moodle scan: reading CHEM 1212 (course 2 of 6)")
        self.assertIn("reading your courses", self.page.locator(".clear.first").inner_text().lower())
        self.status = "Full Moodle scan: reading MATH 1550 (course 3 of 6)"
        self.page.locator("#first-says", has_text="MATH 1550 (course 3 of 6)").wait_for(timeout=9000)

    def test_gradescope_and_connect_are_a_tick_each(self):
        self.page.locator("input[name=gradescope]").check()
        self.page.locator("input[name=mcgraw]").check()
        self.page.locator("#setup-form button[type=submit]").click()
        self.page.locator("#step-look:visible").wait_for()
        self.assertTrue(self.asked[-1]["gradescope"] and self.asked[-1]["mcgraw"])

    def test_it_says_plainly_that_it_isnt_lsus(self):
        self.assertIn("not affiliated with", self.page.locator("#setup-about").inner_text())


class AnotherSchool(FirstRun):
    def choose_other(self):
        self.page.locator("#setup-form label", has_text="Another school").click()
        self.page.locator("input[name=moodle]").wait_for()

    def test_the_addresses_are_asked_for_and_checked(self):
        self.choose_other()
        moodle = self.page.locator("input[name=moodle]")
        self.assertEqual(moodle.input_value(), "")                              # LSU's isn't left in the box
        self.assertEqual(self.page.evaluate("() => document.activeElement.name"), "moodle")
        self.page.keyboard.press("Enter")
        self.page.locator("#setup-form .form-error", has_text="Enter your Moodle address.").wait_for()
        moodle.fill("moodle.example.edu/my/")
        self.page.keyboard.press("Enter")
        self.page.locator("#setup-form .form-error", has_text="should start with https://").wait_for()
        moodle.fill("https://moodle.example.edu/my/")
        self.page.locator("#setup-form label", has_text="Personal (Outlook.com, Hotmail)").click()
        self.page.keyboard.press("Tab")
        self.page.locator("#setup-form button[type=submit]").click()
        self.page.locator("#step-look:visible").wait_for()
        self.assertEqual((self.asked[-1]["moodle"], self.asked[-1]["outlook"]), ("https://moodle.example.edu/my/", "https://outlook.live.com"))

    def test_going_back_to_lsu_fills_them_in_again(self):
        self.choose_other()
        self.page.locator("input[name=moodle]").fill("https://moodle.example.edu")
        self.page.locator("#setup-form label", has_text="LSU").first.click()
        self.assertFalse(self.page.locator("input[name=moodle]").is_visible())
        self.page.locator("#setup-form button[type=submit]").click()
        self.page.locator("#step-look:visible").wait_for()
        self.assertEqual(self.asked[-1]["moodle"], "https://moodle.lsu.edu")


if __name__ == "__main__":
    unittest.main()
