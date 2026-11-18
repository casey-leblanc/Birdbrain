"""Notices on the PC: one at a time, and a click opens the list on that card."""
from __future__ import annotations

import threading
import unittest
from datetime import timedelta

from helpers import NOW, item, store

import notices
import toast
from config import Settings


class FakeIcon:
    """The part of pystray's Windows icon the click is heard through."""

    def __init__(self):
        self.seen = []
        self._message_handlers = {0x0401: self._on_notify, 0x0402: self._on_stop}

    def _on_notify(self, wparam, lparam):
        self.seen.append(lparam)
        return 0

    def _on_stop(self, wparam, lparam):
        return 0


class OneAtATime(unittest.TestCase):
    def setUp(self):
        self.s, self.settings = store(), Settings()
        self.shown, self.opened = [], []
        self.t = toast.Toasts(lambda title, text: self.shown.append(f"{title}: {text}"),
                              notices.Notices(self.s, self.settings), lambda: self.opened.append(1))

    def test_two_due_together_come_half_a_minute_apart_not_as_a_batch(self):
        morning = NOW.replace(hour=9, minute=40)
        self.s.upsert(item("moodle:cm:1", "Pre-lab", morning.replace(hour=23, minute=59), course=""))
        self.s.upsert(item("moodle:cal:4", "Exam 2", morning + timedelta(hours=23), kind="test", course=""))
        self.t.tick(morning)
        self.assertEqual(self.shown, ["Today: Pre-lab"])
        self.t.tick(morning + timedelta(seconds=30))
        self.assertEqual(len(self.shown), 2)
        self.assertTrue(self.shown[1].startswith("Exam tomorrow at 8:40 AM: Exam 2"))
        self.t.tick(morning + timedelta(seconds=60))
        self.assertEqual(len(self.shown), 2)

    def test_new_work_is_said_at_once_and_a_click_opens_on_its_card(self):
        self.t.tell(notices.Notice("new", "New", "Chem Lab 8 report (Thu)", ["moodle:cm:8"]))
        self.assertEqual(self.shown, ["New: Chem Lab 8 report (Thu)"])
        self.assertEqual(self.t.view()["n"], 0)
        self.t.clicked()
        view = self.t.view()
        self.assertEqual((view["n"], view["id"], self.opened), (1, "moodle:cm:8", [1]))
        self.assertGreater(view["at"], 0)

    def test_turned_off_on_the_pc_nothing_shows_but_the_phone_still_hears(self):
        phone = []
        self.t.enabled = lambda: False
        self.t.also.append(lambda n: phone.append(n.line))
        self.t.tell(notices.Notice("new", "New", "Chem Lab 8 report (Thu)", ["moodle:cm:8"]))
        self.assertEqual((self.shown, phone), ([], ["New: Chem Lab 8 report (Thu)"]))

    def test_nothing_to_say_shows_nothing(self):
        self.t.tell(None)
        self.assertIsNone(self.t.tick(NOW))
        self.assertEqual(self.shown, [])

    def test_a_notification_that_cant_be_shown_doesnt_stop_the_next(self):
        def broken(title, text):
            raise OSError("no tray")
        self.t.show = broken
        self.t.tell(notices.Notice("new", "New", "A", ["a"]))
        self.t.show = lambda title, text: self.shown.append(title)
        self.t.tell(notices.Notice("new", "New", "B", ["b"]))
        self.assertEqual(self.shown, ["New"])


class Clicks(unittest.TestCase):
    def test_a_click_on_the_notification_is_heard_and_other_messages_pass_through(self):
        icon, heard = FakeIcon(), threading.Event()
        self.assertTrue(toast.hear_clicks(icon, heard.set))
        handler = icon._message_handlers[0x0401]
        handler(0, 0x0202)                                   # a left click on the icon itself: pystray's business
        self.assertEqual(icon.seen, [0x0202])
        self.assertFalse(heard.is_set())
        handler(0, toast.BALLOON_CLICK)                      # a click on the notification
        self.assertTrue(heard.wait(2))
        self.assertEqual(icon.seen, [0x0202])
        self.assertEqual(icon._message_handlers[0x0402].__name__, "_on_stop")   # nothing else was touched

    def test_an_icon_it_doesnt_know_is_left_alone(self):
        self.assertFalse(toast.hear_clicks(object(), lambda: None))


if __name__ == "__main__":
    unittest.main()
