"""Fixes that came over from later versions: one running copy, catching up after sleep, real times, the sign-in card."""
from __future__ import annotations

import threading
import unittest
from unittest import mock

from helpers import NOW, at, item, store

import instance
import power
import report
from config import Settings


class OneCopy(unittest.TestCase):
    def test_the_lock_is_asked_for_once_however_often_the_answer_is_wanted(self):
        calls = []

        class Kernel:
            def __init__(self):
                self.CreateMutexW = mock.Mock(side_effect=lambda *a: calls.append(a) or 7)

        with mock.patch.object(instance.sys, "platform", "win32"), \
                mock.patch.dict("sys.modules", {"ctypes": mock.Mock(WinDLL=lambda *a, **k: Kernel(),
                                                                    get_last_error=lambda: 0),
                                                "ctypes.wintypes": mock.Mock()}):
            name = "Local\\BirdbrainTest"
            self.assertFalse(instance.already_running(name))
            self.assertFalse(instance.already_running(name))   # asking Windows again would find our own lock
            self.assertEqual(len(calls), 1)

    def test_the_only_copy_starts(self):
        self.assertEqual(instance.start_or_hand_over(["Birdbrain.exe"], running=lambda: False), "start")

    def test_a_second_copy_brings_the_first_ones_window_forward_and_leaves(self):
        shown = []
        todo = instance.start_or_hand_over(["Birdbrain.exe"], running=lambda: True, show=lambda: shown.append(1) or True)
        self.assertEqual((todo, shown), ("leave", [1]))

    def test_a_first_copy_that_cannot_be_reached_is_said_out_loud(self):
        self.assertEqual(instance.start_or_hand_over(["Birdbrain.exe"], running=lambda: True, show=lambda: False), "tell")


class AfterSleep(unittest.TestCase):
    def wait(self, ticks, seconds=3600, wake=None, stop=None):
        clock = iter(ticks)
        wake = wake or mock.Mock(wait=lambda s: False)
        return power.wait(wake, seconds, stop or threading.Event(), clock=lambda: next(clock))

    def test_an_ordinary_hour_passes(self):
        ticks = [0] + [30 * n for n in range(1, 200)]
        self.assertEqual(self.wait(ticks), "due")

    def test_a_pc_that_slept_through_its_scan_time_scans_when_it_wakes(self):
        self.assertEqual(self.wait([0, 30, 60, 60 + 3 * 3600]), "woke")

    def test_a_short_nap_does_not_bring_the_scan_forward(self):
        ticks = [0, 30, 30 + 300] + [330 + 30 * n for n in range(1, 200)]
        self.assertEqual(self.wait(ticks), "due")

    def test_waking_with_a_stale_scan_does_not_wait_out_the_hour(self):
        self.assertEqual(self.wait([0, 30, 30 + 20 * 60], seconds=4 * 3600), "woke")

    def test_being_asked_and_being_stopped(self):
        self.assertEqual(self.wait([0, 30], wake=mock.Mock(wait=lambda s: True)), "asked")
        stop = threading.Event()
        stop.set()
        self.assertEqual(self.wait([0, 30], stop=stop), "stop")

    def test_the_network_is_waited_for_after_a_wake(self):
        tries = []

        def connect(addr, timeout):
            tries.append(addr)
            if len(tries) < 3:
                raise OSError("no network yet")
            return mock.Mock()

        with mock.patch.object(power.time, "sleep"):
            self.assertTrue(power.online("https://moodle.example.edu/my/", connect=connect))
            self.assertEqual(tries, [("moodle.example.edu", 443)] * 3)
            self.assertFalse(power.online("https://moodle.example.edu", tries=2,
                                          connect=mock.Mock(side_effect=OSError)))

    def test_staying_awake_is_harmless_where_it_cannot_be_asked_for(self):
        with power.awake():
            pass


class RealTimes(unittest.TestCase):
    def test_1159_pm_is_a_real_deadline_on_the_sites_that_set_one(self):
        for source in ("moodle", "gradescope", "mcgraw"):
            with self.subTest(source=source):
                self.assertTrue(report.has_time(item(f"{source}:1", due=at(1, 23, 59))))

    def test_a_day_with_no_time_does_not_pretend_to_have_one(self):
        self.assertFalse(report.has_time(item("outlook-mail:1", due=at(1, 23, 59))))
        self.assertFalse(report.has_time(item("manual:1", due=at(1, 23, 59))))
        self.assertFalse(report.has_time(item("outlook-calendar:1", due=at(1, 0, 0))))
        self.assertFalse(report.has_time(item("moodle:page:1", due=at(1, 23, 59))))
        self.assertTrue(report.has_time(item("manual:2", due=at(1, 15, 0))))
        self.assertTrue(report.has_time(item("outlook-calendar:2", due=at(1, 23, 59))))

    def test_the_card_shows_1159_pm_under_the_right_day_and_says_when_there_is_no_time(self):
        s = store()
        s.upsert(item("gradescope:1", "Problem set 9", at(1, 23, 59), course="MATH 1550"))
        s.upsert(item("outlook-mail:2", "Bring a calculator Thursday", at(1, 23, 59), kind="event", course=""))
        b = report.build(s, Settings(), NOW)
        tomorrow = next(g for c in b.columns for g in c.groups if g.label == "Tomorrow")
        self.assertEqual([i.title for i in tomorrow.items], ["Problem set 9", "Bring a calculator Thursday"])
        page = report.render_board(b, Settings(), "", NOW)
        self.assertIn(">11:59 PM</time>", page)
        self.assertEqual(page.count("11:59 PM</time>"), 1)
        self.assertIn("Thursday, November 19, no time given", page)   # what a screen reader hears


class SignInCard(unittest.TestCase):
    def board(self, sign_in):
        s = store()
        s.upsert(item())
        return report.render_board(report.build(s, Settings(), NOW), Settings(), "", NOW, sign_in=sign_in)

    def test_no_card_when_every_site_is_signed_in(self):
        self.assertNotIn("card-sign-in", self.board([]))
        self.assertNotIn("card-sign-in", self.board(None))

    def test_one_site(self):
        page = self.board(["Moodle"])
        self.assertIn("<b>Moodle needs signing in to again.</b>", page)
        self.assertIn('id="card-sign-in"', page)
        self.assertLess(page.index("card-sign-in"), page.index('class="bands"'))   # above the list

    def test_two_sites(self):
        self.assertIn("<b>Moodle and Outlook need signing in to again.</b>", self.board(["Moodle", "Outlook"]))


if __name__ == "__main__":
    unittest.main()
