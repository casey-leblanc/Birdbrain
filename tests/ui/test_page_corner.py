"""The list fills the window. In its corner: a status dot that scans when clicked, and one menu."""
from __future__ import annotations

import unittest

from page import PageTest


class Corner(PageTest):
    def actions(self):
        self.calls = []
        note = lambda name, reply: (lambda body: self.calls.append(name) or reply)
        return {"scan": note("scan", {"ok": True, "state": "started"}), "quit": note("quit", {"ok": True}),
                "update": note("update", {"ok": True, "message": "Birdbrain 2.0.0 is the newest version.", "current": "2.0.0",
                                          "available": "", "packaged": True})}

    def test_the_list_starts_at_the_top_of_the_window(self):
        first = self.page.locator(".band").first.bounding_box()
        self.assertLess(first["y"], 110)   # where the header's date, counts and next-exam strip used to be
        tools = self.page.locator(".tools").bounding_box()
        self.assertLess(tools["y"] + tools["height"], first["y"] + 4)   # the corner tools don't cover the list
        self.assertGreater(tools["x"], 640)                              # and sit to the right

    def test_the_dot_keeps_its_words_to_itself_until_there_is_something_to_read(self):
        dot = self.page.locator("#status-dot")
        self.assertEqual(dot.get_attribute("class"), "status idle")
        self.assertFalse(dot.locator(".st").is_visible())
        dot.hover()
        self.assertTrue(dot.locator(".st").is_visible())
        self.assertEqual(dot.locator(".st").inner_text(), "Updated 10:32 AM.")

    def test_clicking_the_dot_scans(self):
        self.page.locator("#status-dot").click()
        self.page.locator("#toast.show").wait_for()
        self.assertEqual(self.calls, ["scan"])

    def test_the_menu_by_mouse(self):
        self.page.locator("#open-menu").click()
        menu = self.page.locator("#app-menu")
        self.assertEqual(menu.locator("[role=menuitem]").all_inner_texts(),
                         ["Quick write\nSpace", "Search and commands\nCtrl+K", "Add item\nN", "Settings\nS", "Scan now\nR",
                          "Check for updates", "Report a problem", "Quit Birdbrain"])
        menu.get_by_role("menuitem", name="Settings").click()
        self.page.locator("#settings").wait_for(state="visible")
        self.assertFalse(menu.is_visible())

    def test_the_menu_by_keyboard(self):
        self.page.keyboard.press("m")
        menu = self.page.locator("#app-menu")
        menu.wait_for(state="visible")
        self.assertEqual(self.page.evaluate("document.activeElement.dataset.menu"), "quick")
        for _ in range(4):
            self.page.keyboard.press("ArrowDown")
        self.assertEqual(self.page.evaluate("document.activeElement.dataset.menu"), "scan")
        self.page.keyboard.press("End")
        self.assertEqual(self.page.evaluate("document.activeElement.dataset.menu"), "quit")
        self.page.keyboard.press("Escape")
        menu.wait_for(state="hidden")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "open-menu")
        self.page.keyboard.press("Enter")           # open again from the button
        menu.wait_for(state="visible")
        self.page.keyboard.press("ArrowUp")         # wraps to the last
        self.page.keyboard.press("ArrowUp")
        self.assertEqual(self.page.evaluate("document.activeElement.dataset.menu"), "update")
        self.page.keyboard.press("Enter")
        self.page.locator("#update-msg", has_text="newest version").wait_for()
        self.assertEqual(self.calls, ["update"])

    def test_a_click_elsewhere_closes_the_menu(self):
        self.page.locator("#open-menu").click()
        self.page.locator(".band").first.click(position={"x": 5, "y": 5})
        self.page.locator("#app-menu").wait_for(state="hidden")

    def test_add_item_and_quit_from_the_menu(self):
        self.page.locator("#open-menu").click()
        self.page.get_by_role("menuitem", name="Add item").click()
        self.page.locator("#add-item").wait_for(state="visible")
        self.page.keyboard.press("Escape")
        self.page.locator("#add-item").wait_for(state="hidden")
        self.page.locator("#open-menu").click()
        quit = self.page.locator("[data-menu=quit]")
        quit.click()
        self.assertEqual(quit.inner_text(), "Click again to quit")   # quitting can't be undone, so it asks once
        self.assertEqual(self.calls, [])
        quit.click()
        self.page.locator(".gone").wait_for()
        self.assertEqual(self.calls, ["quit"])


class CornerInFocus(Corner):
    layout = "focus"


class NarrowWindow(PageTest):
    def test_on_a_narrow_window_the_tools_still_fit_and_the_list_follows(self):
        self.page.set_viewport_size({"width": 420, "height": 800})
        tools = self.page.locator(".tools").bounding_box()
        first = self.page.locator(".band").first.bounding_box()
        self.assertGreaterEqual(tools["x"], 0)
        self.assertLessEqual(tools["x"] + tools["width"], 420)
        self.assertLess(tools["y"] + tools["height"], first["y"] + 4)


class Problem(PageTest):
    status = "Updated 10:32 AM. Moodle scan failed (see log)."

    def test_a_problem_is_spelled_out_beside_the_dot(self):
        dot = self.page.locator("#status-dot")
        self.assertEqual(dot.get_attribute("class"), "status problem")
        self.assertTrue(dot.locator(".st").is_visible())


if __name__ == "__main__":
    unittest.main()
