"""Snooze: out of sight until a day, back by itself, and never hidden past a deadline."""
from __future__ import annotations

import unittest
from datetime import timedelta

from helpers import NOW, at, item, store

import notices
import report
import snooze
from config import Settings
from server import ListServer

TODAY = NOW.date()          # a Wednesday
D = lambda n: TODAY + timedelta(days=n)


def board(s, now=NOW):
    return report.build(s, Settings(), now)


def on_list(s, now=NOW):
    return [i.id for c in board(s, now).columns for g in c.groups for i in g.items]


class Snoozing(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Essay", at(9)))                      # due in nine days
        self.s.upsert(item("moodle:cm:2", "Lab report", at(2)))                 # due Friday
        self.s.upsert(item("moodle:cm:3", "Reading", at(0)))                    # due tonight
        self.s.upsert(item("moodle:cm:4", "Old worksheet", at(-2)))             # overdue

    def test_a_snoozed_card_leaves_the_list_and_waits_in_archived(self):
        got = snooze.snooze(self.s, "moodle:cm:1", D(1), NOW)
        self.assertEqual((got["until"], got["says"]), (D(1).isoformat(), "Snoozed until tomorrow"))
        self.assertNotIn("moodle:cm:1", on_list(self.s))
        hidden = board(self.s).archived
        self.assertEqual([(h.item.id, h.reason) for h in hidden], [("moodle:cm:1", "Snoozed until tomorrow")])

    def test_it_comes_back_by_itself_and_says_so_for_that_day(self):
        snooze.snooze(self.s, "moodle:cm:1", D(1), NOW)
        tomorrow = NOW + timedelta(days=1)
        self.assertIn("moodle:cm:1", on_list(self.s, tomorrow))
        page = report.render_board(board(self.s, tomorrow), Settings(), "", tomorrow, self.s.version, {})
        self.assertEqual(page.count("back from snooze"), 1)
        after = NOW + timedelta(days=2)
        page = report.render_board(board(self.s, after), Settings(), "", after, self.s.version, {})
        self.assertNotIn("back from snooze", page)                              # only on the day it returns

    def test_it_never_sleeps_past_its_deadline_and_says_so(self):
        got = snooze.snooze(self.s, "moodle:cm:2", D(5), NOW)                   # asked for Monday; it's due Friday
        self.assertEqual(got["until"], D(2).isoformat())
        self.assertEqual(got["says"], "Snoozed until Friday: it's due then, so it can't sleep until Monday")
        self.assertIn("moodle:cm:2", on_list(self.s, NOW + timedelta(days=2)))

    def test_something_due_today_cant_be_snoozed(self):
        with self.assertRaisesRegex(snooze.Refused, "due today"):
            snooze.snooze(self.s, "moodle:cm:3", D(1), NOW)
        self.assertIn("moodle:cm:3", on_list(self.s))

    def test_overdue_work_can_sleep_to_any_day(self):
        got = snooze.snooze(self.s, "moodle:cm:4", D(5), NOW)
        self.assertEqual((got["until"], got["says"]), (D(5).isoformat(), "Snoozed until Monday"))
        self.assertNotIn("moodle:cm:4", on_list(self.s))

    def test_today_or_the_past_is_not_a_day_to_snooze_until(self):
        with self.assertRaisesRegex(snooze.Refused, "after today"):
            snooze.snooze(self.s, "moodle:cm:1", TODAY, NOW)

    def test_waking_it_now_and_undoing_either_way(self):
        got = snooze.snooze(self.s, "moodle:cm:1", D(3), NOW)
        self.assertIsNone(got["was"])
        woke = snooze.snooze(self.s, "moodle:cm:1", None, NOW)
        self.assertEqual((woke["was"], woke["says"]), (D(3).isoformat(), "Back on your list"))
        self.assertIn("moodle:cm:1", on_list(self.s))

    def test_a_scan_doesnt_wake_it(self):
        snooze.snooze(self.s, "moodle:cm:1", D(3), NOW)
        self.s.upsert(item("moodle:cm:1", "Essay (updated)", at(9)))
        self.assertEqual(self.s.get("moodle:cm:1").snoozed, D(3))

    def test_a_sleeping_card_is_left_out_of_notifications(self):
        self.s.upsert(item("moodle:cm:9", "Problem set", NOW.replace(hour=23, minute=59) + timedelta(days=1)))
        snooze.snooze(self.s, "moodle:cm:4", D(2), NOW)
        said = notices.Notices(self.s, Settings()).morning(NOW)
        self.assertNotIn("Old worksheet", said.text)
        self.assertNotIn("overdue", said.text)

    def test_the_choices_say_when_it_would_really_come_back(self):
        far = snooze.choices(self.s.get("moodle:cm:1"), NOW)
        self.assertEqual([(c["label"], c["day"], c["note"]) for c in far],
                         [("Tomorrow", D(1).isoformat(), ""), ("Next week", D(5).isoformat(), "")])
        self.assertEqual(far[1]["says"], "Monday")
        near = snooze.choices(self.s.get("moodle:cm:2"), NOW)
        self.assertEqual((near[1]["day"], near[1]["note"]), (D(2).isoformat(), "it's due Friday, so it comes back then"))

    def test_on_a_sunday_next_week_is_not_tomorrow(self):
        sunday = NOW + timedelta(days=4)
        got = snooze.choices(self.s.get("moodle:cm:4"), sunday)                 # overdue: no deadline to come back for
        self.assertEqual([c["day"] for c in got], [(sunday.date() + timedelta(days=1)).isoformat(),
                                                   (sunday.date() + timedelta(days=8)).isoformat()])


class AsThePageAsks(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.s.upsert(item("moodle:cm:1", "Essay", at(9)))
        self.s.upsert(item("moodle:cm:3", "Reading", at(0)))
        self.srv = ListServer(self.s, render_page=lambda t: "", render_board=lambda t: "", status=lambda: {},
                              request_mail_scan=lambda d: None, on_change=lambda: None)

    def test_ask_snooze_wake(self):
        asked = self.srv.snooze({"id": "moodle:cm:1", "ask": True}, NOW)
        self.assertEqual([c["key"] for c in asked["choices"]], ["tomorrow", "week"])
        self.assertEqual(asked["min"], D(1).isoformat())
        got = self.srv.snooze({"id": "moodle:cm:1", "until": D(1).isoformat()}, NOW)
        self.assertEqual(got["says"], "Snoozed until tomorrow")
        self.assertEqual(self.srv.snooze({"id": "moodle:cm:1", "until": None}, NOW)["says"], "Back on your list")

    def test_what_cant_be_done_is_said_in_one_line(self):
        with self.assertRaisesRegex(ValueError, "due today"):
            self.srv.snooze({"id": "moodle:cm:3", "ask": True}, NOW)
        with self.assertRaisesRegex(ValueError, "isn't a day"):
            self.srv.snooze({"id": "moodle:cm:1", "until": "soon"}, NOW)
        with self.assertRaisesRegex(ValueError, "any more"):
            self.srv.snooze({"id": "nope", "until": D(1).isoformat()}, NOW)


if __name__ == "__main__":
    unittest.main()
