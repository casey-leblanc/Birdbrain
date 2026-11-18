"""Settings > Notifications, and what the page does when a notification is clicked."""
from __future__ import annotations

import time
import unittest

from page import PageTest


class NotificationSettings(PageTest):
    def setUp(self):
        self.asked: list[dict] = []
        super().setUp()

    def actions(self) -> dict:
        def notifications(body: dict) -> dict:
            self.asked.append(body)
            if body.get("test"):
                return {"ok": True, "message": "Sent: “Due tonight: Chem Exp 15 Quiz”. Look by the clock."}
            return {"ok": True, "message": "Saved." if body.get("on") else "Notifications are off. Your list still updates by itself."}
        return {"notifications": notifications}

    def open_pane(self):
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Notifications").click()

    def test_they_are_on_with_times_that_suit_most_students(self):
        self.open_pane()
        self.assertTrue(self.page.locator("#notify-on").is_checked())
        self.assertEqual(self.page.locator("#notify-morning").input_value(), "07:30")
        self.assertEqual(self.page.locator("#notify-evening").input_value(), "19:00")
        self.assertTrue(self.page.locator("#notify-tests").is_checked())
        self.assertEqual(self.asked, [])                                        # looking changes nothing

    def test_a_changed_time_is_saved_as_it_is_made(self):
        self.open_pane()
        self.page.locator("#notify-evening").fill("21:15")
        self.page.locator("#notify-evening").dispatch_event("change")
        self.page.locator("#notify-msg", has_text="Saved.").wait_for()
        self.assertEqual(self.asked[-1], {"on": True, "morning": "07:30", "evening": "21:15", "tests": True})

    def test_turning_them_off_greys_the_rest_and_says_so(self):
        self.open_pane()
        self.page.locator("#notify-on").uncheck()
        self.page.locator("#notify-msg", has_text="Notifications are off").wait_for()
        self.assertTrue(self.page.locator("#notify-morning").is_disabled())
        self.assertTrue(self.page.locator("#notify-tests").is_disabled())
        self.assertFalse(self.asked[-1]["on"])
        self.page.locator("#notify-on").focus()                                 # and back on, by keyboard
        self.page.keyboard.press("Space")
        self.page.locator("#notify-msg", has_text="Saved.").wait_for()
        self.assertFalse(self.page.locator("#notify-morning").is_disabled())

    def test_show_me_one_sends_one_and_says_what_it_said(self):
        self.open_pane()
        self.page.locator("#notify-test").click()
        self.page.locator("#notify-msg", has_text="Sent:").wait_for()
        self.assertEqual(self.asked, [{"test": True}])


class ClickedNotification(PageTest):
    def test_the_open_window_moves_to_the_card_it_was_about(self):
        self.page.keyboard.press("s")                                           # even with Settings in the way
        self.page.locator("#settings[open]").wait_for()
        self.focus = {"n": 1, "id": "moodle:cm:3", "at": time.time()}
        row = self.page.locator(".row.landed")
        row.wait_for(timeout=9000)
        self.assertIn("Urease", row.inner_text())
        self.assertEqual(self.page.locator("dialog[open]").count(), 0)
        focused = self.page.evaluate("() => document.activeElement.closest('.row').dataset.id")
        self.assertEqual(focused, "moodle:cm:3")
        self.assertIn("Urease", self.page.locator("#announce").text_content())

    def test_a_card_in_completed_opens_the_bin(self):
        self.store.set_done("moodle:cm:3", True)
        self.page.reload()
        self.page.wait_for_selector(".row")
        self.focus = {"n": 1, "id": "moodle:cm:3", "at": time.time()}
        self.page.locator(".bin.completed .row.landed").wait_for(timeout=9000)
        self.assertTrue(self.page.locator(".bin.completed").evaluate("d => d.open"))


class WindowOpenedByTheClick(PageTest):
    focus = {"n": 1, "id": "moodle:cm:3", "at": time.time() + 3600}             # clicked a moment before the window came up

    def test_a_fresh_window_goes_straight_to_the_card(self):
        self.page.locator(".row.landed").wait_for(timeout=9000)
        self.assertEqual(self.page.evaluate("() => document.activeElement.closest('.row').dataset.id"), "moodle:cm:3")


class AnOldClick(PageTest):
    focus = {"n": 4, "id": "moodle:cm:3", "at": 1000.0}                         # clicked long ago

    def test_opening_the_window_later_doesnt_jump_anywhere(self):
        self.page.wait_for_timeout(6500)
        self.assertEqual(self.page.locator(".row.landed").count(), 0)


if __name__ == "__main__":
    unittest.main()
