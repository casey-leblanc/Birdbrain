"""S on a card: until tomorrow, next week or a picked day; it waits in Archived and can be woken."""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from page import PageTest


class Snooze(PageTest):
    def press_s_on(self, title: str):
        self.row(title).locator(".tick").focus()
        self.page.keyboard.press("s")
        self.page.locator("#snooze[open]").wait_for()

    def toast(self) -> str:
        return self.page.locator("#toast span").first.inner_text()

    def test_s_then_t_snoozes_until_tomorrow_with_no_mouse(self):
        self.press_s_on("Urease")
        self.assertEqual(self.page.locator("#settings[open]").count(), 0, "S on a card snoozes; it doesn't open Settings")
        self.assertIn("Snooze “Biochemical Testing - Urease Test” until", self.page.locator("#snz-title").inner_text())
        self.page.keyboard.press("t")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.toast(), "Snoozed until tomorrow")
        self.assertEqual(self.stored("moodle:cm:3").snoozed, date.today() + timedelta(days=1))
        self.assertEqual(self.page.locator(".bands .row", has_text="Urease").count(), 0)
        hidden = self.page.locator(".bin.archived .row", has_text="Urease")
        self.assertEqual(hidden.count(), 1)
        self.assertIn("Snoozed until tomorrow", hidden.locator(".detail").text_content())
        focused = self.page.evaluate("() => document.activeElement.closest('.row') && document.activeElement.closest('.row').dataset.id")
        self.assertIsNotNone(focused, "focus moves to a neighbouring card")

    def test_undo_brings_it_straight_back(self):
        self.press_s_on("Urease")
        self.page.keyboard.press("t")
        self.page.locator(".toast-undo").click()
        self.page.locator(".bands .row", has_text="Urease").wait_for()
        self.assertIsNone(self.stored("moodle:cm:3").snoozed)

    def test_next_week_past_a_deadline_says_so_before_and_after(self):
        self.press_s_on("Urease")                                               # due in three days
        today = date.today()
        if today + timedelta(days=3) < today + timedelta(days=(7 - today.weekday()) or 7):
            note = self.page.locator("#snz-list button").nth(1).locator("small").inner_text()
            self.assertIn("so it comes back then", note)
            self.page.keyboard.press("w")
            self.page.locator(".toast-undo").wait_for()
            self.assertIn("it's due then, so it can't sleep until", self.toast())
            self.assertEqual(self.stored("moodle:cm:3").snoozed, today + timedelta(days=3))
        else:                                                                   # run on a day when Monday comes first
            self.page.keyboard.press("w")
            self.page.locator(".toast-undo").wait_for()
            self.assertLessEqual(self.stored("moodle:cm:3").snoozed, today + timedelta(days=3))

    def test_a_picked_day(self):
        self.press_s_on("Essay 2 draft")                                        # overdue: any day will do
        day = date.today() + timedelta(days=4)
        self.page.keyboard.press("p")
        self.assertEqual(self.page.evaluate("() => document.activeElement.id"), "snz-day")
        self.page.locator("#snz-day").fill(day.isoformat())
        self.page.keyboard.press("Enter")
        self.page.locator(".toast-undo").wait_for()
        self.assertEqual(self.stored("moodle:cm:6").snoozed, day)
        self.assertEqual(self.page.locator("#snz-day").get_attribute("min"), (date.today() + timedelta(days=1)).isoformat())

    def test_something_due_today_says_why_not(self):
        self.row("Oxidase").locator(".tick").focus()
        self.page.keyboard.press("s")
        self.page.locator("#toast", has_text="due today, so it can't be snoozed").wait_for()
        self.assertEqual(self.page.locator("#snooze[open]").count(), 0)

    def test_the_button_on_the_card_and_esc(self):
        row = self.row("Urease")
        row.hover()
        row.locator(".act.snooze").click()
        self.page.locator("#snooze[open]").wait_for()
        self.assertEqual(self.page.locator("#snz-list button").count(), 2)
        self.page.keyboard.press("Escape")
        self.page.locator("#snooze").wait_for(state="hidden")
        self.assertIsNone(self.stored("moodle:cm:3").snoozed)

    def test_wake_it_now_from_archived(self):
        self.store.snooze("moodle:cm:3", date.today() + timedelta(days=2))
        self.page.reload()
        self.page.wait_for_selector(".row")
        self.page.locator(".bin.archived summary").click()
        hidden = self.page.locator(".bin.archived .row", has_text="Urease")
        hidden.locator(".act.wake").click()
        self.page.locator(".bands .row", has_text="Urease").wait_for()
        self.assertIsNone(self.stored("moodle:cm:3").snoozed)
        self.assertEqual(self.toast(), "Back on your list")

    def test_the_day_it_returns_the_card_says_so(self):
        self.store.snooze("moodle:cm:3", date.today())
        self.page.reload()
        self.page.wait_for_selector(".row")
        self.assertEqual(self.row("Urease").locator(".snz").inner_text(), "back from snooze")

    def test_s_away_from_a_card_is_still_settings_and_the_keys_sheet_says_both(self):
        self.page.keyboard.press("s")
        self.page.locator("#settings[open]").wait_for()
        self.page.keyboard.press("Escape")
        self.page.locator("#settings").wait_for(state="hidden")
        self.page.keyboard.press("?")
        keys = self.page.locator("#keys")
        self.assertIn("Snooze it until a day", keys.inner_text())
        self.assertTrue(keys.evaluate("d => d.scrollHeight <= d.clientHeight + 1"), "the keys still fit one screen")


class SnoozeInFocus(Snooze):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
