"""Settings in plain order, with everything most students never need folded away under Advanced."""
from __future__ import annotations

import unittest

from page import PageTest

ORDER = ["Sign-ins", "Look", "Notifications", "Keys", "Labels", "Updates", "About", "Advanced"]


class SettingsOrder(PageTest):
    def open_settings(self):
        self.page.keyboard.press("s")
        self.page.locator("#settings[open]").wait_for()

    def test_the_sections_come_in_plain_order_and_advanced_is_last(self):
        self.open_settings()
        tabs = self.page.locator("#settings [role=tab]")
        self.assertEqual([t.strip() for t in tabs.all_inner_texts()], ORDER)
        self.assertEqual(self.page.locator("#settings [role=tab][aria-selected=true]").inner_text().strip(), "Sign-ins")
        self.assertTrue(self.page.locator("#sign-in").is_visible())             # the first thing: the Sign in button
        self.assertEqual(self.page.locator("#settings [role=tablist]").get_attribute("aria-orientation"), "vertical")

    def test_arrow_keys_walk_the_list(self):
        self.open_settings()
        self.page.locator("#tab-signins").focus()
        self.page.keyboard.press("ArrowDown")
        self.assertTrue(self.page.locator("#pane-look").is_visible())
        self.page.keyboard.press("ArrowUp")
        self.page.keyboard.press("ArrowUp")                                     # round to the end
        self.assertTrue(self.page.locator("#pane-advanced").is_visible())
        self.page.keyboard.press("Home")
        self.assertTrue(self.page.locator("#pane-signins").is_visible())

    def test_every_part_of_advanced_is_closed_until_opened(self):
        self.open_settings()
        self.page.get_by_role("tab", name="Advanced").click()
        folds = self.page.locator("#pane-advanced details.fold")
        self.assertGreaterEqual(folds.count(), 5)
        self.assertEqual(self.page.locator("#pane-advanced details.fold[open]").count(), 0)
        for hidden in ("#addr-moodle", "#scan-full", "#scan-since", "#kw-input", "[data-open=log]"):
            self.assertFalse(self.page.locator(hidden).is_visible(), hidden)
        self.page.locator("#fold-keywords summary").click()
        self.assertTrue(self.page.locator("#kw-input").is_visible())
        self.page.locator("#fold-keywords summary").focus()                     # and by keyboard
        self.page.keyboard.press("Enter")
        self.assertFalse(self.page.locator("#kw-input").is_visible())

    def test_what_moved_is_where_a_student_would_look(self):
        self.open_settings()
        for tab, thing in (("Notifications", "#sound-on"), ("Keys", "#keys-sec"), ("Labels", "#label-new"),
                           ("Labels", "#classes-sec"), ("Updates", "#update-check"), ("About", "#about-sec")):
            self.page.get_by_role("tab", name=tab).click()
            self.assertTrue(self.page.locator(thing).first.is_visible(), f"{thing} under {tab}")

    def test_check_for_updates_in_the_menu_lands_on_updates(self):
        self.page.keyboard.press("m")
        self.page.locator("#app-menu [data-menu=update]").click()
        self.assertTrue(self.page.locator("#pane-updates").is_visible())


class SettingsInFocus(SettingsOrder):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
