"""The system-wide shortcut: choosing it in Settings, and the small window's page it opens."""
from __future__ import annotations

import unittest
from unittest import mock

from page import PageTest

import hotkey
from test_hotkey import FakeKeys


class ShortcutInSettings(PageTest):
    def setUp(self):
        patch = mock.patch.object(hotkey, "available", lambda: True)
        patch.start()
        self.addCleanup(patch.stop)
        self.saved = []
        self.shortcut = hotkey.Shortcut(FakeKeys(taken=["ctrl+alt+q"]), save=self.saved.append)
        self.shortcut.start("ctrl+alt+space")
        super().setUp()
        self.page.keyboard.press("s")
        self.page.get_by_role("tab", name="Keys").click()
        self.msg = self.page.locator("#hotkey-msg")

    def hotkey_view(self):
        return self.shortcut.view()

    def actions(self):
        return {"hotkey": self.shortcut.use}

    def test_change_listens_for_the_next_shortcut_pressed(self):
        self.assertIn("Ctrl+Alt+Space anywhere on your PC", self.msg.inner_text())
        self.page.locator("#hotkey-change").click()
        self.assertIn("Press the new shortcut", self.page.locator("#hotkey-change").inner_text())
        self.page.keyboard.press("Control+Shift+K")
        self.page.locator("#hotkey-msg", has_text="Ctrl+Shift+K is ready").wait_for()
        self.assertEqual(self.saved, ["ctrl+shift+k"])
        self.assertTrue(self.page.locator("#settings").is_visible())      # the keys went to the listener, not the page

    def test_a_taken_shortcut_is_said_and_another_is_one_click_away(self):
        self.page.locator("#hotkey-change").click()
        self.page.keyboard.press("Control+Alt+Q")
        self.page.locator("#hotkey-msg", has_text="Another program is already using Ctrl+Alt+Q").wait_for()
        self.assertIn("Ctrl+Alt+Space still works", self.msg.inner_text())
        self.page.locator("#hotkey-offers button").first.click()
        self.page.locator("#hotkey-msg", has_text="is ready").wait_for()
        self.assertEqual(self.page.locator("#hotkey-offers button").count(), 0)
        self.assertEqual(self.saved, ["ctrl+shift+space"])

    def test_escape_while_listening_cancels_and_keeps_settings_open(self):
        self.page.locator("#hotkey-change").click()
        self.page.keyboard.press("Escape")
        self.assertEqual(self.page.locator("#hotkey-change").inner_text(), "Change the shortcut")
        self.assertTrue(self.page.locator("#settings").is_visible())
        self.assertEqual(self.shortcut.keys.asked, ["ctrl+alt+space"])

    def test_off_and_on(self):
        self.page.locator("#hotkey-off").click()
        self.page.locator("#hotkey-msg", has_text="The shortcut is off").wait_for()
        self.assertFalse(self.page.locator("#hotkey-off").is_visible())
        self.page.locator("#hotkey-on").click()
        self.page.locator("#hotkey-msg", has_text="Ctrl+Alt+Space is ready").wait_for()
        self.assertEqual(self.saved, ["", "ctrl+alt+space"])


class SmallWindow(PageTest):
    def setUp(self):
        super().setUp()
        self.page.goto(self.server.url.replace("/?token=", "/quick?token="))
        self.line = self.page.locator("#quick-line")
        self.line.wait_for()

    def actions(self):
        self.hidden = []
        return {"quick-hide": lambda body: self.hidden.append(1) or {"ok": True}}

    def test_it_is_ready_to_type_in_and_saves_without_the_main_window(self):
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "quick-line")
        self.page.keyboard.type("chem lab report fri 5pm #life")
        self.page.locator(".chip[data-what=label]", has_text="Life").wait_for()
        self.assertEqual(self.page.locator(".chip").all_inner_texts()[1:], ["5:00 PM", "Life"])
        self.page.keyboard.press("Enter")
        self.page.locator("#quick-chips.saved", has_text="Added “Chem lab report” for").wait_for()
        self.page.wait_for_timeout(1000)
        self.assertEqual(self.hidden, [1])                                 # the small window asks to be put away
        self.assertEqual(self.line.input_value(), "")
        mine = [i for i in self.store.items_between(*self.far()) if i.title == "Chem lab report"]
        self.assertEqual((len(mine), mine[0].label, mine[0].due.hour), (1, "life", 17))

    def test_ctrl_enter_keeps_it_open_for_another(self):
        self.page.keyboard.type("one")
        self.page.keyboard.press("Control+Enter")
        self.page.locator("#quick-chips.saved", has_text="Added “One”").wait_for()
        self.page.keyboard.type("two")
        self.page.keyboard.press("Control+Enter")
        self.page.locator("#quick-chips.saved", has_text="Added “Two”").wait_for()
        self.page.wait_for_timeout(1400)
        self.assertEqual(self.hidden, [])

    def test_escape_puts_it_away_and_saves_nothing(self):
        self.page.keyboard.type("never mind")
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        self.assertEqual(self.hidden, [1])
        self.assertEqual([i for i in self.store.items_between(*self.far()) if i.title == "Never mind"], [])

    def far(self):
        from datetime import datetime, timedelta
        return datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=400)


class NoSmallWindow(PageTest):
    def test_where_there_is_no_small_window_the_list_opens_quick_write_itself(self):
        self.page.wait_for_timeout(300)
        type(self).quick_asks = 1                                          # the shortcut was pressed
        try:
            self.page.locator("#quick-line").wait_for(state="visible", timeout=15000)
        finally:
            type(self).quick_asks = 0


if __name__ == "__main__":
    unittest.main()
