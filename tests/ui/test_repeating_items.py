"""A repeating item, from Space to the next one: typed in quick write, ticked off, and the next appears."""
from __future__ import annotations

import unittest

from page import PageTest


class Repeating(PageTest):
    def mine(self):
        return [i for i in self.store.open_items() if i.source == "manual" and i.title == "Gym"]

    def add_gym(self):
        self.page.keyboard.press("Space")
        self.page.locator("#quick-line").wait_for()
        self.page.keyboard.type("gym every day 11:59pm")
        self.page.locator("#quick-chips .chip[data-what=repeat]").wait_for()
        chips = self.page.locator("#quick-chips .chip").all_inner_texts()
        self.page.keyboard.press("Enter")
        self.page.locator(".row.landed").wait_for()
        return chips

    def test_quick_write_reads_it_and_the_card_says_it_repeats(self):
        chips = self.add_gym()
        self.assertIn("Every day", chips)
        row = self.row("Gym")
        self.assertEqual(row.locator(".rep").inner_text(), "every day")
        self.assertEqual(self.mine()[0].repeat, "daily")

    def test_ticking_it_brings_the_next_one_and_says_when(self):
        self.add_gym()
        first = self.mine()[0]
        self.page.keyboard.press("Escape")
        self.row("Gym").locator(".tick").click()
        self.page.locator("#toast", has_text="The next one is tomorrow.").wait_for()
        (nxt,) = self.mine()
        self.assertNotEqual(nxt.id, first.id)
        self.assertEqual(self.group_of(self.page.locator(f".bands .row[data-id='{nxt.id}']")), "tomorrow")
        self.page.locator(".toast-undo").click()                                # Undo: back to the one, and only one
        self.page.locator("#toast", has_text="Put back").wait_for()
        self.assertEqual([i.id for i in self.mine()], [first.id])
        self.assertEqual(self.page.locator(".bands .row", has_text="Gym").count(), 1)

    def test_the_details_sheet_shows_it_and_can_stop_it(self):
        self.add_gym()
        self.row("Gym").locator(".tick").focus()
        self.page.keyboard.press("e")
        box = self.page.locator("#add-form input[name=repeats]")
        box.wait_for()
        self.assertEqual(box.input_value(), "every day")
        box.fill("sometimes")
        self.page.locator("#add-form button[type=submit]").click()
        self.page.locator("#add-form .form-error", has_text="how often").wait_for()
        box.fill("every mon wed")
        self.page.locator("#add-form button[type=submit]").click()
        self.page.locator("#toast", has_text="Saved").wait_for()
        self.page.locator("#add-item").wait_for(state="hidden")
        self.assertEqual(self.mine()[0].repeat, "weekly:0,2")
        self.assertEqual(self.row("Gym").locator(".rep").inner_text(), "every mon, wed")
        self.row("Gym").locator(".tick").focus()
        self.page.keyboard.press("e")
        box.fill("")
        self.page.locator("#add-form button[type=submit]").click()
        self.page.locator(".row .rep").wait_for(state="detached")
        self.assertEqual(self.mine()[0].repeat, "")

    def test_a_card_from_a_site_has_no_repeat_to_set(self):
        self.row("Urease").locator(".tick").focus()
        self.page.keyboard.press("e")
        box = self.page.locator("#add-form input[name=repeats]")
        box.wait_for()
        self.assertTrue(box.is_disabled())
        self.assertEqual(box.input_value(), "")


class RepeatingInFocus(Repeating):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
