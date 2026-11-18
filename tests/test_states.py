"""The states in between: each says what is going on and what to do, in one line."""
from __future__ import annotations

import unittest
from datetime import timedelta

from helpers import NOW, item, store

import report
import states
from config import Settings

GONE = Exception("Page.goto: net::ERR_INTERNET_DISCONNECTED at https://moodle.lsu.edu/my/")
NO_SUCH = Exception("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://moodel.lsu.edu/")
CHANGED = Exception("Locator.wait_for: Timeout 30000ms exceeded waiting for locator('.timeline-event-list')")


def one_line(text: str) -> bool:
    return "\n" not in text and len(text) <= 190


class AfterAScan(unittest.TestCase):
    def test_all_well_is_quiet(self):
        self.assertEqual(states.status("10:32 AM", [], 2), "Updated 10:32 AM.")
        self.assertEqual(report.status_state("Updated 10:32 AM."), "idle")

    def test_every_site_out_of_reach_is_being_offline_said_once(self):
        both = [states.problem("Moodle", GONE, "https://moodle.lsu.edu"), states.problem("Outlook", GONE, "https://outlook.office.com")]
        self.assertTrue(states.offline(both, 2))
        line = states.status("10:32 AM", both, 2)
        self.assertEqual(line, "You're offline. Your list is as it was; Birdbrain scans again as soon as you're back online.")
        self.assertEqual(report.status_state(line), "note")                     # worth reading, but nothing is broken
        self.assertTrue(one_line(line))

    def test_one_site_out_of_reach_names_it_and_says_what_to_check(self):
        trouble = [states.problem("Moodle", NO_SUCH, "https://moodel.lsu.edu")]
        self.assertFalse(states.offline(trouble, 2))
        line = states.status("10:32 AM", trouble, 2)
        self.assertEqual(line, "Updated 10:32 AM. Couldn't reach Moodle at moodel.lsu.edu: check your connection, or the address "
                               "in Settings › Advanced.")
        self.assertEqual(report.status_state(line), "problem")
        self.assertTrue(one_line(line))

    def test_a_site_that_changed_says_the_list_is_as_it_was_and_to_look_for_an_update(self):
        trouble = [states.problem("Moodle", CHANGED, "https://moodle.lsu.edu")]
        self.assertEqual(trouble[0].kind, "changed")
        line = states.status("10:32 AM", trouble, 2)
        self.assertEqual(line, "Updated 10:32 AM. Moodle couldn't be read: its page may have changed. Your list is as it was; "
                               "check for updates in the menu.")
        self.assertEqual(report.status_state(line), "problem")
        self.assertTrue(one_line(line))

    def test_signing_in_again_keeps_the_words_the_page_looks_for(self):
        line = states.status("10:32 AM", [states.Problem("Outlook", "sign-in")], 2)
        self.assertEqual(line, "Updated 10:32 AM. Outlook needs sign-in.")
        self.assertEqual(report.status_state(line), "problem")

    def test_a_scan_that_crashed_says_what_happens_next(self):
        self.assertEqual(report.status_state(states.DIDNT_FINISH), "problem")
        self.assertIn("Report a problem", states.DIDNT_FINISH)
        self.assertTrue(one_line(states.DIDNT_FINISH))

    def test_a_site_with_no_address_is_still_named(self):
        self.assertTrue(states.Problem("Gradescope", "unreachable").line.startswith("Couldn't reach Gradescope: check"))


class TheListsOwn(unittest.TestCase):
    """Nothing due today, everything done, the first scan still running: the list says which, where the cards would be."""

    def page(self, s, status="Updated 10:32 AM.", now=NOW):
        return report.render_board(report.build(s, Settings(), now), Settings(), status, now, s.version, {})

    def test_nothing_due_today(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Essay", NOW + timedelta(days=1)))
        self.assertIn("nothing due today", self.page(s))

    def test_everything_done_for_today(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Reading", NOW.replace(hour=23, minute=59)))
        s.upsert(item("moodle:cm:2", "Essay", NOW + timedelta(days=1)))
        s.set_done("moodle:cm:1", True)
        from datetime import datetime
        now = datetime.now()                                                    # ticked just now, so judged by the real clock
        s.upsert(item("moodle:cm:1", "Reading", now.replace(hour=23, minute=59)))
        s.upsert(item("moodle:cm:2", "Essay", now + timedelta(days=1)))
        self.assertIn("nothing left for today", self.page(s, now=now))

    def test_nothing_at_all_says_all_clear_and_what_is_next(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Essay", NOW + timedelta(days=4)))
        page = self.page(s)
        self.assertIn("all clear", page)
        self.assertIn("Next up: <b>Essay</b>", page)

    def test_the_first_scan_still_running_says_what_it_is_reading(self):
        page = self.page(store(), "Full Moodle scan in progress…")
        self.assertIn("reading your courses", page)
        self.assertIn('id="first-says" aria-live="polite">Full Moodle scan in progress…', page)
        self.assertNotIn("all clear", page)                                     # an empty list isn't a result yet

    def test_offline_keeps_the_list_and_says_so_at_the_top(self):
        s = store()
        s.upsert(item("moodle:cm:1", "Essay", NOW + timedelta(days=1)))
        page = self.page(s, states.OFFLINE)
        self.assertIn("You&#x27;re offline." if "&#x27;" in page else "You're offline.", page)
        self.assertIn("Essay", page)
        self.assertIn('class="status note"', page)


if __name__ == "__main__":
    unittest.main()
