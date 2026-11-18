"""The keyboard: Space is quick write now, X ticks, E opens details, ? shows every key, J/K cross day groups."""
from __future__ import annotations

import unittest

from page import PageTest


class Keys(PageTest):
    def focused_title(self):
        return self.page.evaluate("(document.activeElement.closest('.row')||{querySelector(){return {textContent:''}}})"
                                  ".querySelector('.t').textContent")

    def test_space_on_a_card_opens_quick_write_and_ticks_nothing(self):
        self.page.keyboard.press("j")
        first = self.focused_title()
        self.page.keyboard.press("Space")
        self.page.locator("#quick-line").wait_for(state="visible")
        self.page.keyboard.press("Escape")
        self.assertFalse(self.row(first).locator(".tick").is_checked())
        self.assertEqual(self.page.locator(".bin.completed .row").count(), 0)

    def test_x_ticks_the_focused_card_and_undo_brings_it_back(self):
        self.page.keyboard.press("j")
        first = self.focused_title()
        self.page.keyboard.press("x")
        self.page.locator(".bin.completed .row", has_text=first).wait_for(state="attached")
        self.assertIsNotNone(self.stored("moodle:cm:6").done_at)          # the overdue essay is first on the list
        self.assertNotEqual(self.focused_title(), first)                   # focus moved on to the next card
        self.page.locator("#toast", has_text="Moved to Completed").wait_for()
        self.page.keyboard.press("Control+z")
        self.page.locator(".bands .row", has_text=first).wait_for()
        self.assertIsNone(self.stored("moodle:cm:6").done_at)

    def test_x_on_a_completed_card_unticks_it(self):
        self.store.set_done("manual:7", True)
        self.open()
        self.page.locator(".bin.completed summary").click()
        self.page.locator(".bin.completed .row .tick").focus()
        self.page.keyboard.press("x")
        self.page.locator(".bands .row", has_text="Dentist").wait_for()
        self.assertIsNone(self.stored("manual:7").done_at)

    def test_e_opens_a_cards_details(self):
        self.row("Dentist").locator(".tick").focus()            # one of yours: the form, filled in
        self.page.keyboard.press("e")
        self.page.locator("#add-item").wait_for(state="visible")
        self.assertEqual(self.page.locator("#add-form [name=title]").input_value(), "Dentist")
        self.page.keyboard.press("Escape")
        self.page.locator("#add-item").wait_for(state="hidden")
        self.row("Exam 2").locator(".tick").focus()             # one from Moodle: what it is
        self.page.keyboard.press("e")
        self.page.locator("#kind-dialog").wait_for(state="visible")

    def test_question_mark_shows_every_key_on_one_screen(self):
        self.page.keyboard.press("?")
        sheet = self.page.locator("#keys")
        sheet.wait_for(state="visible")
        text = sheet.inner_text()
        for words in ("Quick write", "Tick it off, or untick it", "Its details", "Open the menu", "Save and add another"):
            self.assertIn(words, text)
        self.assertNotIn("Space\nTick", text)
        box = sheet.bounding_box()
        self.assertLessEqual(box["height"], 900)
        self.assertTrue(sheet.evaluate("d => d.scrollHeight <= d.clientHeight + 1"), "the keys don't fit one screen")
        self.page.keyboard.press("Escape")
        sheet.wait_for(state="hidden")

    def test_j_k_and_the_arrows_walk_every_card_through_the_day_groups(self):
        focused = lambda: self.page.evaluate("document.activeElement.closest('.row').dataset.id")
        want = self.page.locator(".bands .row").evaluate_all("rows => rows.map(r => r.dataset.id)")
        seen, groups = [], []
        self.page.keyboard.press("j")
        for n in range(len(want)):
            seen.append(focused())
            groups.append(self.page.evaluate(
                "document.activeElement.closest('ul').previousElementSibling.textContent.trim().toLowerCase()"))
            self.page.keyboard.press("j" if n % 2 else "ArrowDown")
        self.assertEqual(seen, want)
        self.assertGreaterEqual(len(set(groups)), 4)            # overdue, today, tomorrow, and days further on
        self.page.keyboard.press("k")
        self.page.keyboard.press("ArrowUp")
        self.assertEqual(focused(), want[-3])


class KeysInFocus(Keys):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
