"""One line, Ctrl+K or "/": it narrows the list as you type, and it runs things."""
from __future__ import annotations

import unittest

from page import PageTest


class SearchAndCommands(PageTest):
    def setUp(self):
        self.scans = 0
        super().setUp()

    def actions(self) -> dict:
        def scan(body: dict) -> dict:
            self.scans += 1
            return {"ok": True, "state": "started"}
        return {"scan": scan}

    def open_line(self, key: str = "Control+k"):
        self.page.keyboard.press(key)
        self.page.locator("#filter[open]").wait_for()

    def shown(self) -> list[str]:
        return [t.strip() for t in self.page.locator(".bands .row:visible .t").evaluate_all("els => els.map(e => e.firstChild.textContent)")]

    def commands(self) -> list[str]:
        return self.page.locator("#cmd-list li span").all_inner_texts()

    def chosen(self) -> str:
        picked = self.page.locator("#cmd-list li[aria-selected=true] span")
        return picked.inner_text() if picked.count() else ""

    def test_ctrl_k_and_slash_both_open_it_with_the_commands_listed(self):
        self.open_line()
        self.assertEqual(self.page.evaluate("() => document.activeElement.id"), "filter-line")
        listed = self.commands()
        for name in ("Scan now", "Settings", "New label", "Night", "Show the keys"):
            self.assertIn(name, listed)
        self.assertEqual(self.chosen(), "")                                     # nothing runs by accident
        self.page.keyboard.press("Escape")
        self.page.locator("#filter").wait_for(state="hidden")
        self.open_line("/")
        self.assertEqual(self.page.locator("#filter-line").input_value(), "")   # the slash itself isn't typed

    def test_typing_a_word_narrows_the_list_and_enter_keeps_it(self):
        self.open_line()
        self.page.keyboard.type("biochem")
        self.assertEqual(len(self.shown()), 3)
        self.assertEqual(self.commands(), [])                                   # no command answers to that
        self.page.keyboard.press("Enter")
        self.page.locator("#filter").wait_for(state="hidden")
        self.assertEqual(len(self.shown()), 3)
        self.assertIn("biochem", self.page.locator("#filter-chip").inner_text())
        self.page.keyboard.press("Escape")                                      # Esc on the list shows everything
        self.page.locator("#filter-chip").wait_for(state="detached")
        self.assertEqual(len(self.shown()), 7)

    def test_esc_in_the_line_closes_it_and_shows_everything(self):
        self.open_line()
        self.page.keyboard.type("exam")
        self.assertEqual(self.shown(), ["Exam 2"])
        self.page.keyboard.press("Escape")
        self.page.locator("#filter").wait_for(state="hidden")
        self.assertEqual(len(self.shown()), 7)

    def test_a_command_is_chosen_when_what_is_typed_starts_its_name_and_enter_runs_it(self):
        self.open_line()
        self.page.keyboard.type("sc")
        self.assertEqual(self.chosen(), "Scan now")
        self.assertEqual(len(self.shown()), 7, "a line that is plainly a command doesn't hide the list")
        self.page.keyboard.press("Enter")
        self.page.locator("#filter").wait_for(state="hidden")
        self.page.locator("#toast.show").wait_for()
        self.assertEqual(self.scans, 1)

    def test_settings_new_label_and_keys(self):
        self.open_line()
        self.page.keyboard.type("settings")
        self.page.keyboard.press("Enter")
        self.page.locator("#settings[open]").wait_for()
        self.page.keyboard.press("Escape")
        self.page.locator("#settings").wait_for(state="hidden")
        self.open_line()
        self.page.keyboard.type("new label")
        self.assertEqual(self.chosen(), "New label")
        self.page.keyboard.press("Enter")
        self.page.locator("#pane-labels").wait_for()
        self.assertEqual(self.page.evaluate("() => document.activeElement.id"), "label-new")
        self.page.keyboard.press("Escape")
        self.page.locator("#settings").wait_for(state="hidden")
        self.open_line()
        self.page.keyboard.type("short")                                        # another word it answers to
        self.assertEqual(self.chosen(), "Show the keys")
        self.page.keyboard.press("Enter")
        self.page.locator("#keys[open]").wait_for()

    def test_night_and_day_switch_and_are_kept(self):
        import prefs
        self.open_line()
        self.page.keyboard.type("day")
        self.page.keyboard.press("Enter")
        self.page.locator("html[data-mode=light]").wait_for()
        self.open_line()
        self.page.keyboard.type("night")
        self.page.keyboard.press("Enter")
        self.page.locator("html[data-mode=dark]").wait_for()
        self.page.locator("#toast", has_text="Night").wait_for()
        self.assertEqual(prefs.load(self.store)["mode"], "dark")

    def test_arrow_keys_choose_and_the_mouse_can_too(self):
        self.open_line()
        self.page.keyboard.press("ArrowDown")
        first = self.chosen()
        self.assertEqual(first, self.commands()[0])
        self.page.keyboard.press("ArrowDown")
        self.assertEqual(self.chosen(), self.commands()[1])
        self.assertEqual(self.page.locator("#filter-line").get_attribute("aria-activedescendant"),
                         self.page.locator("#cmd-list li[aria-selected=true]").get_attribute("id"))
        self.page.keyboard.press("ArrowUp")
        self.page.keyboard.press("ArrowUp")                                     # back off the list: nothing chosen
        self.assertEqual(self.chosen(), "")
        self.page.locator("#cmd-list li", has_text="Show the keys").click()
        self.page.locator("#keys[open]").wait_for()

    def test_a_word_inside_a_command_name_still_just_filters(self):
        self.open_line()
        self.page.keyboard.type("quiz")                                         # no command starts with it
        self.assertEqual(self.chosen(), "")
        self.assertEqual(self.shown(), ["Chapter 7 Quiz"])
        self.page.keyboard.press("Enter")
        self.assertEqual(self.shown(), ["Chapter 7 Quiz"])

    def test_hash_and_at_still_start_it_off(self):
        self.open_line("@")
        self.assertEqual(self.page.locator("#filter-line").input_value(), "@")
        self.page.keyboard.type("math")
        self.assertEqual(self.commands(), [])
        self.assertEqual(sorted(self.shown()), ["Chapter 7 Quiz", "Exam 2"])

    def test_it_is_in_the_menu_and_on_the_keys_sheet(self):
        self.page.keyboard.press("m")
        self.page.locator("#app-menu [data-menu=find]").click()
        self.page.locator("#filter[open]").wait_for()
        self.page.keyboard.press("Escape")
        self.page.keyboard.press("?")
        self.assertIn("Search, or run a command", self.page.locator("#keys").inner_text())


class InFocus(SearchAndCommands):
    layout = "focus"


if __name__ == "__main__":
    unittest.main()
