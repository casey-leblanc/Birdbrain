"""What is this? One answer on one card fixes the whole series, on the page and in the store."""
from __future__ import annotations

import unittest

from page import PageTest


class WhatIsThis(PageTest):
    def test_saying_a_lab_is_an_assignment_fixes_the_series(self):
        lab = self.row("Oxidase Test")
        self.assertEqual(lab.locator(".kind").inner_text().lower(), "exam")   # what the old rules said
        lab.hover()
        lab.locator(".act.whatis").click()
        dialog = self.page.locator("#kind-dialog")
        dialog.wait_for(state="visible")
        self.assertIn("Oxidase Test", dialog.locator(".kind-name").inner_text())
        self.assertEqual(dialog.locator("[aria-pressed=true]").inner_text(), "Exam")
        dialog.get_by_role("button", name="Assignment").click()
        self.page.locator("#toast", has_text="2 more like it").wait_for()
        dialog.wait_for(state="hidden")
        for title in ("Oxidase Test", "Catalase Test", "Urease Test"):
            self.assertEqual(self.row(title).locator(".kind").count(), 0, title)
        self.assertEqual(self.row("Exam 2").locator(".kind").inner_text().lower(), "exam")   # a real exam stays one
        self.assertEqual([self.stored(f"moodle:cm:{n}").kind for n in (1, 2, 3)], ["assignment"] * 3)

    def test_keyboard_only_and_escape_changes_nothing(self):
        button = self.row("Chapter 7 Quiz").locator(".act.whatis")
        button.focus()
        self.page.keyboard.press("Enter")
        dialog = self.page.locator("#kind-dialog")
        dialog.wait_for(state="visible")
        self.assertEqual(dialog.locator("[aria-pressed=true]").inner_text(), "Quiz")
        self.page.keyboard.press("Escape")
        dialog.wait_for(state="hidden")
        self.assertEqual(self.stored("moodle:cm:5").level, "quiz")

    def test_your_own_items_have_edit_instead(self):
        self.assertEqual(self.row("Dentist").locator(".act.whatis").count(), 0)


class WhatIsThisInFocus(WhatIsThis):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
