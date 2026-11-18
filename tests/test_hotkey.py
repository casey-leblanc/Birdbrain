"""The system-wide shortcut for quick write: how it's written, what Settings is told, and (on Windows) the real thing."""
from __future__ import annotations

import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

from helpers import NOW, item, store

import hotkey
import prefs
import report
from config import Settings
from server import ListServer


class FakeKeys:
    """Stands in for Windows: some shortcuts belong to other programs."""

    def __init__(self, taken=()):
        self.taken, self.combo, self.asked = set(taken), "", []

    def set(self, combo):
        self.asked.append(combo)
        if combo in self.taken:
            return f"Another program is already using {hotkey.say(combo)}."   # the one in force stays
        self.combo = combo
        return ""


class Written(unittest.TestCase):
    def test_tidied_to_one_spelling(self):
        self.assertEqual(hotkey.tidy("Ctrl + Alt+SPACE"), "ctrl+alt+space")
        self.assertEqual(hotkey.tidy("space+alt+control"), "ctrl+alt+space")
        self.assertEqual(hotkey.tidy("shift+ctrl+k"), "ctrl+shift+k")
        self.assertEqual(hotkey.tidy("meta+f5"), "win+f5")

    def test_said_the_way_keys_are_printed(self):
        self.assertEqual(hotkey.say("ctrl+alt+space"), "Ctrl+Alt+Space")
        self.assertEqual(hotkey.say(hotkey.tidy("win+shift+f5")), "Shift+Win+F5")
        self.assertEqual(hotkey.say(hotkey.tidy("alt+shift+q")), "Alt+Shift+Q")
        self.assertEqual(hotkey.say(""), "")

    def test_what_windows_is_asked_for(self):
        self.assertEqual(hotkey.parse("ctrl+alt+space"), (0x0002 | 0x0001, 0x20))
        self.assertEqual(hotkey.parse("ctrl+shift+k"), (0x0002 | 0x0004, ord("K")))
        self.assertEqual(hotkey.parse("alt+f12"), (0x0001, 0x7B))

    def test_shortcuts_that_would_be_typed_by_accident_are_refused(self):
        for bad, why in (("space", "needs Ctrl, Alt"), ("shift+a", "needs Ctrl, Alt"), ("ctrl+alt", "needs one key"),
                         ("ctrl+a+b", "needs one key"), ("ctrl+enter", "needs one key"), ("", "needs one key")):
            with self.subTest(combo=bad), self.assertRaisesRegex(ValueError, why):
                hotkey.tidy(bad)

    def test_others_to_offer_never_include_the_one_that_failed(self):
        self.assertEqual(len(hotkey.others("ctrl+alt+space")), 3)
        self.assertNotIn("ctrl+alt+space", hotkey.others("ctrl+alt+space"))


class InSettings(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(hotkey, "available", lambda: True)
        p.start()
        self.addCleanup(p.stop)
        self.saved = []

    def shortcut(self, taken=()):
        return hotkey.Shortcut(FakeKeys(taken), save=self.saved.append)

    def test_the_saved_shortcut_comes_into_force_at_start(self):
        s = self.shortcut()
        self.assertEqual(s.start("ctrl+alt+space"), "")
        self.assertEqual((s.view()["combo"], s.view()["label"], s.view()["problem"]), ("ctrl+alt+space", "Ctrl+Alt+Space", ""))

    def test_a_shortcut_another_program_has_is_said_with_others_to_try(self):
        s = self.shortcut(taken=["ctrl+alt+space"])
        self.assertIn("Another program is already using Ctrl+Alt+Space", s.start("ctrl+alt+space"))
        view = s.view()
        self.assertEqual(view["combo"], "")
        self.assertEqual([c["label"] for c in view["suggest"]], ["Ctrl+Shift+Space", "Ctrl+Alt+Q", "Alt+Shift+Q"])
        got = s.use({"combo": view["suggest"][0]["combo"]})          # the student takes the first offer
        self.assertEqual((got["combo"], got["problem"], got["suggest"]), ("ctrl+shift+space", "", []))
        self.assertIn("Ctrl+Shift+Space is ready", got["message"])
        self.assertEqual(self.saved, ["ctrl+shift+space"])

    def test_asking_for_a_taken_one_keeps_the_one_that_works(self):
        s = self.shortcut(taken=["ctrl+alt+q"])
        s.start("ctrl+alt+space")
        got = s.use({"combo": "Ctrl+Alt+Q"})
        self.assertIn("Another program is already using Ctrl+Alt+Q. Ctrl+Alt+Space still works.", got["message"])
        self.assertEqual(got["combo"], "ctrl+alt+space")
        self.assertNotIn("ctrl+alt+space", [c["combo"] for c in got["suggest"]])   # not offered: it's the one in use
        self.assertEqual(self.saved, [])                             # nothing is saved until one works

    def test_off_and_on_again(self):
        s = self.shortcut()
        s.start("ctrl+alt+space")
        off = s.use({"combo": ""})
        self.assertEqual((off["combo"], self.saved), ("", [""]))
        self.assertIn("The shortcut is off", off["message"])
        on = s.use({"on": True})
        self.assertEqual((on["combo"], self.saved), ("ctrl+alt+space", ["", "ctrl+alt+space"]))

    def test_a_shortcut_that_is_not_one_is_explained_and_changes_nothing(self):
        s = self.shortcut()
        s.start("ctrl+alt+space")
        got = s.use({"combo": "shift+a"})
        self.assertIn("needs Ctrl, Alt or the Windows key", got["message"])
        self.assertEqual((got["combo"], self.saved), ("ctrl+alt+space", []))

    def page(self, view):
        s = store()
        s.upsert(item())
        return report.render(report.build(s, Settings(), NOW), Settings(), "", NOW, "tok", hotkey=view)

    def test_settings_says_which_shortcut_and_offers_to_change_it(self):
        s = self.shortcut()
        s.start("ctrl+alt+space")
        sec = self.page(s.view()).split('id="hotkey-sec"')[1].split('id="updates-sec"')[0]
        self.assertIn("<kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Space</kbd> anywhere on your PC", sec)
        self.assertIn('id="hotkey-change"', sec)
        self.assertIn('id="hotkey-on" hidden', sec)

    def test_settings_says_when_it_is_taken_and_shows_the_offers(self):
        s = self.shortcut(taken=["ctrl+alt+space"])
        s.start("ctrl+alt+space")
        sec = self.page(s.view()).split('id="hotkey-sec"')[1].split('id="updates-sec"')[0]
        self.assertIn("Another program is already using Ctrl+Alt+Space.", sec)
        self.assertIn('data-hotkey="ctrl+shift+space">Use Ctrl+Shift+Space</button>', sec)

    def test_where_there_is_no_such_thing_settings_says_so(self):
        with mock.patch.object(hotkey, "available", lambda: False):
            sec = self.page(self.shortcut().view()).split('id="hotkey-sec"')[1].split('id="updates-sec"')[0]
        self.assertIn("on Windows only for now", sec)
        self.assertNotIn("hotkey-change", sec)


class SmallWindowPage(unittest.TestCase):
    def test_the_page_is_the_line_and_nothing_else(self):
        page = report.render_quick("tok", prefs.DEFAULTS)
        self.assertIn('id="quick-line"', page)
        self.assertIn('content="tok"', page)
        for absent in ('class="bands"', 'id="settings"', 'id="app-menu"'):
            self.assertNotIn(absent, page)

    def test_it_is_served_only_with_the_key(self):
        s = store()
        srv = ListServer(s, render_page=lambda t, **k: "", render_board=lambda t: "", status=lambda: {},
                         request_mail_scan=lambda d: None, on_change=lambda: None,
                         render_quick=lambda t: report.render_quick(t, prefs.load(s)))
        srv.start()
        try:
            base = f"http://127.0.0.1:{srv.port}/quick"
            self.assertIn("quick-line", urllib.request.urlopen(f"{base}?token={srv.token}").read().decode())
            with self.assertRaises(urllib.error.HTTPError) as refused:
                urllib.request.urlopen(base)
            self.assertEqual(refused.exception.code, 403)
        finally:
            srv.stop()


@unittest.skipUnless(os.name == "nt", "the real shortcut is Windows'")
class RealWindows(unittest.TestCase):
    COMBO = "ctrl+alt+shift+f11"   # unlikely to belong to anything on a build machine

    def test_register_press_and_a_second_program_is_told_it_is_taken(self):
        import ctypes
        pressed = threading.Event()
        first = hotkey.Hotkey(pressed.set)
        self.addCleanup(first.stop)
        self.assertEqual(first.set(self.COMBO), "")
        self.assertEqual(first.combo, self.COMBO)
        second = hotkey.Hotkey(lambda: None)
        self.addCleanup(second.stop)
        self.assertEqual(second.set("ctrl+alt+shift+f10"), "")
        why = second.set(self.COMBO)                                 # taken: the one it had keeps working
        self.assertIn("Another program is already using Ctrl+Alt+Shift+F11", why)
        self.assertEqual(second.combo, "ctrl+alt+shift+f10")
        ctypes.WinDLL("user32").PostThreadMessageW(first._tid, 0x0312, 1, 0)   # what Windows sends on a press
        self.assertTrue(pressed.wait(5), "the press never reached Birdbrain")
        self.assertEqual(first.set(""), "")                          # off: now the second program can have it
        self.assertEqual(first.combo, "")
        time.sleep(0.2)
        self.assertEqual(second.set(self.COMBO), "")


if __name__ == "__main__":
    unittest.main()
