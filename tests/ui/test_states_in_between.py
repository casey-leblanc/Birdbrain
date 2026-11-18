"""When a scan didn't go as it should, the line beside the dot says what is going on and what to do."""
from __future__ import annotations

import unittest

from page import PageTest

import states


class Offline(PageTest):
    status = states.OFFLINE

    def test_the_line_is_there_to_read_and_the_list_is_still_the_list(self):
        dot = self.page.locator("#status-dot")
        self.assertIn("note", dot.get_attribute("class"))                       # calm, not red: nothing is broken
        self.assertTrue(dot.locator(".st").is_visible())
        self.assertEqual(dot.locator(".st").inner_text(), states.OFFLINE)
        self.assertEqual(self.page.locator(".bands .row").count(), 7)
        self.assertEqual(self.page.locator("#card-sign-in").count(), 0)


class ASiteThatChanged(PageTest):
    status = states.status("10:32 AM", [states.Problem("Moodle", "changed")], 2)

    def test_it_says_the_list_is_as_it_was_and_to_check_for_updates(self):
        dot = self.page.locator("#status-dot")
        self.assertIn("problem", dot.get_attribute("class"))
        text = dot.locator(".st").inner_text()
        self.assertTrue(dot.locator(".st").is_visible())
        self.assertIn("Moodle couldn't be read", text)
        self.assertIn("check for updates in the menu", text)
        self.assertEqual(self.page.locator(".bands .row").count(), 7)
        self.page.keyboard.press("m")                                           # and the menu has it
        self.assertTrue(self.page.locator("#app-menu [data-menu=update]").is_visible())


class GoingOfflineWhileOpen(PageTest):
    def test_the_line_appears_without_a_reload_and_is_read_out(self):
        self.status = states.OFFLINE
        self.page.locator("#status-dot .st", has_text="You're offline.").wait_for(timeout=9000)
        self.assertIn("note", self.page.locator("#status-dot").get_attribute("class"))


if __name__ == "__main__":
    unittest.main()
