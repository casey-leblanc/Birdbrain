"""Quick write in the window: Space, type, Enter. No mouse."""
from __future__ import annotations

import unittest
from page import PageTest


class QuickWrite(PageTest):
    def open(self):
        super().open()
        self.line = self.page.locator("#quick-line")
        self.chips = self.page.locator("#quick-chips .chip")

    def type(self, text):
        self.page.keyboard.press("Space")
        self.line.wait_for(state="visible")
        self.page.keyboard.type(text)

    def test_space_opens_one_line_with_today_as_the_starting_guess(self):
        self.page.keyboard.press("Space")
        self.line.wait_for(state="visible")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "quick-line")
        self.assertEqual(self.chips.all_inner_texts(), ["Today"])

    def test_chips_say_what_was_understood_as_you_type(self):
        self.type("dentist tmr 3pm #app")
        self.page.locator("#quick-chips .chip[data-what=label]").wait_for()
        self.assertEqual(self.chips.all_inner_texts(), ["Tomorrow", "3:00 PM", "Appointment"])

    def test_enter_saves_and_the_card_lands_in_its_day(self):
        self.type("call the bank tmr 9am #life")
        self.page.locator("#quick-chips .chip[data-what=label]").wait_for()
        self.page.keyboard.press("Enter")
        self.line.wait_for(state="hidden")
        card = self.row("Call the bank")
        card.wait_for()
        self.assertEqual(card.locator("time").inner_text(), "9:00 AM")
        self.assertEqual(card.locator(".lab").inner_text(), "Life")
        self.assertEqual(self.group_of(card), "tomorrow")
        self.page.locator("#toast", has_text="Added “Call the bank” for Tomorrow").wait_for()
        self.assertEqual(self.page.evaluate("document.activeElement.closest('.row').querySelector('.t').textContent"),
                         "Call the bank")   # focus is on the new card, ready for the next key

    def test_ctrl_enter_saves_and_stays_for_another(self):
        self.type("first thing")
        self.page.keyboard.press("Control+Enter")
        self.row("First thing").wait_for()
        self.assertTrue(self.line.is_visible())
        self.assertEqual(self.line.input_value(), "")
        self.page.keyboard.type("second thing")
        self.page.keyboard.press("Enter")
        self.row("Second thing").wait_for()
        self.line.wait_for(state="hidden")

    def test_escape_closes_and_saves_nothing(self):
        before = self.page.locator(".row").count()
        self.type("never mind")
        self.page.keyboard.press("Escape")
        self.line.wait_for(state="hidden")
        self.assertEqual(self.page.locator(".row").count(), before)

    def test_backspace_right_after_a_word_it_read_hands_the_word_back(self):
        self.type("tmr")
        self.page.locator("#quick-chips .chip", has_text="Tomorrow").wait_for()
        self.page.keyboard.press("Backspace")
        self.page.locator("#quick-chips .chip", has_text="Today").wait_for()
        self.assertEqual(self.line.input_value(), "tmr")   # the word is still there, now as plain text
        self.page.keyboard.type(" never dies")
        self.page.keyboard.press("Enter")
        card = self.row("Tmr never dies")
        card.wait_for()
        self.assertEqual(self.group_of(card), "today")
        self.page.keyboard.press("Space")                  # and the next line starts fresh: tmr is read again
        self.page.keyboard.type("tmr")
        self.page.locator("#quick-chips .chip", has_text="Tomorrow").wait_for()

    def test_undo_takes_it_back(self):
        self.type("mistake")
        self.page.keyboard.press("Enter")
        self.row("Mistake").wait_for()
        self.page.keyboard.press("Control+z")
        self.page.locator("#toast", has_text="Removed").wait_for()
        self.assertEqual(self.row("Mistake").count(), 0)

    def test_space_does_not_open_it_while_typing_elsewhere(self):
        self.page.keyboard.press("n")                      # Add item's form
        self.page.locator("#add-item").wait_for(state="visible")
        self.page.keyboard.type("two words")
        self.assertFalse(self.line.is_visible())
        self.assertEqual(self.page.locator("#add-form [name=title]").input_value(), "two words")

    def test_something_far_off_is_saved_and_says_when_it_will_show(self):
        self.type("renew passport in 300 days")
        self.page.keyboard.press("Enter")
        self.page.locator("#toast", has_text="It will show on your list when it is closer").wait_for()


class QuickWriteInFocus(QuickWrite):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
